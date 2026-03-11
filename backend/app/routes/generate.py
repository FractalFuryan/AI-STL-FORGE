import asyncio
import json
import os
from io import BytesIO
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from app.models import GenerationParams
from app.services.cache import STLCache
from app.services.stl_generator import STLGenerator

router = APIRouter(prefix="/api", tags=["generation"])
_generator = STLGenerator()
_cache = STLCache()

MAX_IMAGE_DIMENSION = 8192
MIN_IMAGE_DIMENSION = 8


def validate_and_load_image(contents: bytes) -> Image.Image:
    try:
        with Image.open(BytesIO(contents)) as test_img:
            test_img.verify()
        with Image.open(BytesIO(contents)) as img:
            img.load()
            return img.copy()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image format.") from exc
    except SyntaxError as exc:
        raise HTTPException(status_code=400, detail="Corrupted image file.") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid or corrupted image.") from exc


def start_cache_cleanup() -> None:
    _cache.start_background_cleanup()


async def shutdown_cache_cleanup() -> None:
    await _cache.stop_background_cleanup()


def get_cache() -> STLCache:
    return _cache


def get_generator() -> STLGenerator:
    return _generator


@router.get("/stats")
def get_stats() -> dict[str, Any]:
    return _cache.stats()


@router.post("/generate-stl")
async def generate_stl(image: UploadFile = File(...), params: str = Form("{}")) -> Response:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    try:
        payload = json.loads(params)
        parsed = GenerationParams(**payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid params: {exc}") from exc

    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Image file is empty.")

    img = validate_and_load_image(data)
    width, height = img.size

    if min(width, height) < MIN_IMAGE_DIMENSION:
        raise HTTPException(status_code=400, detail="Image dimensions are too small.")

    if max(width, height) > MAX_IMAGE_DIMENSION:
        raise HTTPException(
            status_code=413,
            detail=f"Image dimensions exceed maximum of {MAX_IMAGE_DIMENSION}px.",
        )

    cache_key = _cache.generate_key(data, parsed.model_dump(), version="2.0")
    cached = _cache.get(cache_key)
    if cached is not None:
        return Response(
            content=cached,
            media_type="model/stl",
            headers={
                "Content-Disposition": 'attachment; filename="model.stl"',
                "X-Cache": "HIT",
                "X-Cache-Key": cache_key[:16],
            },
        )

    timeout_seconds = int(os.getenv("GENERATION_TIMEOUT", "30"))
    try:
        stl_bytes = await asyncio.wait_for(
            _generator.generate_stl_async(data, parsed),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=408, detail=f"Generation timed out after {timeout_seconds}s.") from exc

    _cache.set(cache_key, stl_bytes)
    return Response(
        content=stl_bytes,
        media_type="model/stl",
        headers={
            "Content-Disposition": 'attachment; filename="model.stl"',
            "X-Cache": "MISS",
            "X-Cache-Key": cache_key[:16],
        },
    )
