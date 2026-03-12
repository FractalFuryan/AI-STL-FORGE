from contextlib import asynccontextmanager
import io
import json
import time
import uuid
import zipfile
from typing import Any

import os
import psutil
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.middleware import rate_limiter, validate_limits
from app.metrics import ACTIVE_REQUESTS, RATE_LIMIT_BLOCKED, REQUEST_COUNT, REQUEST_DURATION, render_metrics
from app.routes.action_figure import router as action_figure_router
from app.routes.busts import router as busts_router
from app.routes.creatures import router as creatures_router
from app.routes.generate import router as generate_router
from app.routes.reconstruct import router as reconstruct_router
from app.routes.statue import router as statue_router
from app.routes.tabletop import router as tabletop_router
from app.routes.generate import (
    get_cache,
    get_generator,
    shutdown_cache_cleanup,
    start_cache_cleanup,
    validate_and_load_image,
)
from app.models import GenerationParams
from app.services.depth_estimator import depth_estimator

STARTUP_TIME = time.time()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await rate_limiter.initialize()
    start_cache_cleanup()
    if os.getenv("PRELOAD_AI", "false").lower() == "true" and depth_estimator.check_available():
        await depth_estimator.load_model()
    yield
    await shutdown_cache_cleanup()
    if depth_estimator.model is not None:
        depth_estimator.cleanup()
    await rate_limiter.close()


app = FastAPI(
    title="AI STL Forge API",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.middleware("http")
async def add_api_guardrails(request: Request, call_next):
    start = time.time()
    client_ip = request.client.host if request.client and request.client.host else "unknown"
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    endpoint = request.url.path
    method = request.method
    ACTIVE_REQUESTS.inc()

    if not await rate_limiter.check_limit(client_ip):
        remaining = await rate_limiter.get_remaining(client_ip)
        RATE_LIMIT_BLOCKED.inc()
        response = JSONResponse(
            status_code=429,
            content={
                "error": "Too many requests",
                "retry_after": 60,
                "remaining": remaining,
                "limiter_mode": rate_limiter.mode,
                "request_id": request_id,
            },
            headers={
                "X-RateLimit-Limit": str(rate_limiter.requests_per_minute),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Mode": rate_limiter.mode,
                "X-Request-ID": request_id,
                "Retry-After": "60",
            },
        )
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status="429").inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.time() - start)
        ACTIVE_REQUESTS.dec()
        return response

    limit_response = await validate_limits(request)
    if limit_response is not None:
        status = str(getattr(limit_response, "status_code", 400))
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(time.time() - start)
        ACTIVE_REQUESTS.dec()
        return limit_response

    response = await call_next(request)
    duration = time.time() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}"
    response.headers["X-RateLimit-Limit"] = str(rate_limiter.requests_per_minute)
    response.headers["X-RateLimit-Remaining"] = str(await rate_limiter.get_remaining(client_ip))
    response.headers["X-RateLimit-Mode"] = rate_limiter.mode
    response.headers["X-Request-ID"] = request_id
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=str(response.status_code)).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
    ACTIVE_REQUESTS.dec()
    return response


@app.get("/api/health")
def health() -> dict[str, Any]:
    cache = get_cache()
    generator = get_generator()

    deps_available = depth_estimator.check_available()
    ai_loaded = depth_estimator.model is not None

    process = psutil.Process()
    memory_info = process.memory_info()
    try:
        open_files = len(process.open_files())
    except (psutil.AccessDenied, NotImplementedError):
        open_files = None

    cache_healthy = cache.is_healthy()
    generator_healthy = generator.is_healthy()
    status = "healthy" if cache_healthy and generator_healthy else "degraded"

    return {
        "status": status,
        "version": "2.0",
        "uptime_seconds": int(time.time() - STARTUP_TIME),
        "ai": {
            "available": deps_available,
            "loaded": ai_loaded,
            "model": depth_estimator.model_name if deps_available else None,
            "device": str(depth_estimator.device) if ai_loaded else None,
        },
        "cache": cache.get_stats(),
        "system": {
            "memory_usage_mb": memory_info.rss / (1024 * 1024),
            "cpu_percent_system": psutil.cpu_percent(interval=0.0),
            "cpu_percent_process": process.cpu_percent(interval=0.0),
            "open_files": open_files,
            "threads": process.num_threads(),
        },
        "rate_limiter": {
            "requests_per_minute": rate_limiter.requests_per_minute,
            "active_ips": len(rate_limiter.requests),
            "mode": rate_limiter.mode,
        },
    }


@app.get("/api/version")
def version_info() -> dict[str, str]:
    return {
        "version": app.version,
        "build_time": os.getenv("BUILD_TIME", "unknown"),
        "commit": os.getenv("GIT_COMMIT", "unknown"),
        "branch": os.getenv("GIT_BRANCH", "unknown"),
        "environment": os.getenv("ENVIRONMENT", "development"),
    }


@app.get("/api/metrics")
def metrics() -> Response:
    payload, content_type = render_metrics()
    return Response(content=payload, media_type=content_type)


def _require_admin(request: Request) -> None:
    token = os.getenv("ADMIN_TOKEN")
    header = request.headers.get("Authorization")
    if not token or header != f"Bearer {token}":
        raise HTTPException(status_code=403, detail="Admin access required")


@app.post("/api/admin/cache/clear")
def admin_clear_cache(request: Request) -> dict[str, int | str]:
    _require_admin(request)
    cache = get_cache()
    removed = cache.clear()
    return {"status": "cache_cleared", "entries_removed": removed}


@app.post("/api/admin/ai/unload")
def admin_unload_ai(request: Request) -> dict[str, str]:
    _require_admin(request)
    if depth_estimator.model is not None:
        depth_estimator.cleanup()
        return {"status": "model_unloaded"}
    return {"status": "no_model_loaded"}


@app.post("/api/generate-batch")
async def generate_batch(
    images: list[UploadFile] = File(...),
    params: str = Form("{}"),
) -> Response:
    if len(images) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images per batch")

    try:
        payload = json.loads(params)
        parsed = GenerationParams(**payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid params: {exc}") from exc

    cache = get_cache()
    generator = get_generator()
    archive = io.BytesIO()

    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for index, upload in enumerate(images, start=1):
            data = await upload.read()
            if not data:
                continue

            _ = validate_and_load_image(data)
            key = cache.generate_key(data, parsed.model_dump(), version=app.version)
            cached = cache.get(key)
            if cached is not None:
                zipf.writestr(f"model_{index}.stl", cached)
                continue

            stl_bytes = await generator.generate_stl_async(data, parsed)
            cache.set(key, stl_bytes)
            zipf.writestr(f"model_{index}.stl", stl_bytes)

    archive.seek(0)
    batch_id = str(uuid.uuid4())[:8]
    return Response(
        content=archive.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="stl_batch_{batch_id}.zip"'},
    )


def _ai_recommendation(status: str) -> str:
    if status == "unavailable":
        return "Install AI dependencies: pip install -r requirements-ai.txt"
    if status == "not_loaded":
        return "Use POST /api/health/warmup to pre-load the model"
    return "AI depth estimation is ready"


@app.get("/api/health/ai")
def ai_health() -> dict[str, Any]:
    deps_available = depth_estimator.check_available()
    if not deps_available:
        status = "unavailable"
    elif depth_estimator.model is None:
        status = "not_loaded"
    else:
        status = "loaded"

    return {
        "status": status,
        "model": depth_estimator.model_name if deps_available else None,
        "device": str(depth_estimator.device) if depth_estimator.model is not None else None,
        "dependencies_installed": deps_available,
        "can_load": deps_available,
        "recommended_action": _ai_recommendation(status),
    }


@app.post("/api/health/warmup")
async def warmup_model(background_tasks: BackgroundTasks, request: Request) -> dict[str, Any]:
    if not depth_estimator.check_available():
        raise HTTPException(
            status_code=400,
            detail="AI dependencies not installed. Run: pip install -r requirements-ai.txt",
        )

    if depth_estimator.model is not None:
        return {
            "status": "already_loaded",
            "model": depth_estimator.model_name,
            "device": str(depth_estimator.device),
            "message": "Model already loaded",
        }

    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        auth_header = request.headers.get("Authorization")
        expected_token = os.getenv("ADMIN_TOKEN")
        if expected_token and auth_header != f"Bearer {expected_token}":
            raise HTTPException(status_code=403, detail="Admin access required")

    async def _load_model_background() -> None:
        await depth_estimator.load_model()

    background_tasks.add_task(_load_model_background)
    return {
        "status": "loading_started",
        "message": "Model loading in background. Check /api/health/ai for status.",
    }


@app.get("/api/health/live")
def health_live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/api/health/ready")
def health_ready():
    cache = get_cache()
    generator = get_generator()

    if not cache.is_healthy():
        return JSONResponse(status_code=503, content={"status": "not_ready", "reason": "cache_unhealthy"})

    if not generator.is_healthy():
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "generator_unhealthy"},
        )

    return {"status": "ready"}


app.include_router(generate_router)
app.include_router(tabletop_router)
app.include_router(action_figure_router)
app.include_router(creatures_router)
app.include_router(busts_router)
app.include_router(reconstruct_router)
app.include_router(statue_router)
