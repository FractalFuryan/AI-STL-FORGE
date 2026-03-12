from __future__ import annotations

import logging
import os
import shutil
import tempfile
import uuid
from io import BytesIO
from pathlib import Path

import trimesh
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from app.ai.depth import estimate_depth
from app.ai.reconstructor import reconstruct_mesh_sf3d, reconstruct_mesh_triposr, resolve_model
from app.ai.segmentation import remove_background
from app.mesh.export import scale_and_export
from app.mesh.remesh import decimate_mesh
from app.mesh.repair import repair_mesh

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reconstruct", tags=["AI Reconstruction"])

# In-memory status store suitable for single-process deployments.
job_status: dict[str, dict] = {}
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MIN_IMAGE_DIMENSION = 16
MAX_IMAGE_DIMENSION = 8192


def _safe_unlink(path: str | None) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def _validate_upload(image: UploadFile, content: bytes) -> None:
    if not image.content_type or image.content_type.lower() not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a PNG, JPEG, or WEBP image.",
        )

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image file is too large. Max size is {MAX_UPLOAD_BYTES // (1024 * 1024)}MB.",
        )

    try:
        with Image.open(BytesIO(content)) as test_img:
            test_img.verify()
        with Image.open(BytesIO(content)) as img:
            img.load()
            width, height = img.size
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image format") from exc
    except (SyntaxError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Corrupted image file") from exc

    if min(width, height) < MIN_IMAGE_DIMENSION:
        raise HTTPException(status_code=400, detail="Image dimensions are too small")
    if max(width, height) > MAX_IMAGE_DIMENSION:
        raise HTTPException(
            status_code=413,
            detail=f"Image dimensions exceed maximum of {MAX_IMAGE_DIMENSION}px",
        )


@router.post("/3d")
async def reconstruct_3d(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    model: str = Form("auto"),
    preset: str = Form("balanced"),
    target_height_mm: float = Form(150.0),
    output_format: str = Form("stl"),
    repair: bool = Form(True),
    decimate_ratio: float | None = Form(0.6),
    remove_bg: bool = Form(False),
) -> dict[str, str]:
    if preset not in {"fast", "balanced", "high"}:
        raise HTTPException(status_code=400, detail="Preset must be 'fast', 'balanced', or 'high'")

    if model not in {"auto", "sf3d", "triposr"}:
        raise HTTPException(status_code=400, detail="Model must be 'auto', 'sf3d', or 'triposr'")
    if output_format not in {"stl", "glb"}:
        raise HTTPException(status_code=400, detail="Output format must be 'stl' or 'glb'")
    if target_height_mm <= 0:
        raise HTTPException(status_code=400, detail="target_height_mm must be greater than 0")
    if decimate_ratio is not None and not (0.1 <= float(decimate_ratio) <= 1.0):
        raise HTTPException(status_code=400, detail="decimate_ratio must be between 0.1 and 1.0")

    resolved_model = resolve_model(model, preset)

    job_id = str(uuid.uuid4())
    content = await image.read()
    _validate_upload(image, content)

    suffix = Path(image.filename or "upload.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"

    fd, input_path = tempfile.mkstemp(suffix=suffix, prefix=f"recon_input_{job_id}_")
    os.close(fd)

    with open(input_path, "wb") as f:
        f.write(content)

    job_status[job_id] = {
        "status": "processing",
        "progress": 1,
        "model": resolved_model,
        "preset": preset,
        "format": output_format,
    }

    background_tasks.add_task(
        process_reconstruction_job,
        job_id,
        input_path,
        resolved_model,
        target_height_mm,
        output_format,
        repair,
        decimate_ratio,
        remove_bg,
    )

    return {"job_id": job_id, "status": "processing"}


@router.get("/3d/status/{job_id}")
async def get_job_status(job_id: str) -> dict:
    status = job_status.get(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")

    payload = dict(status)
    if payload.get("status") == "completed":
        payload["download_url"] = f"/api/reconstruct/3d/download/{job_id}"
        if payload.get("preview_path"):
            payload["preview_url"] = f"/api/reconstruct/3d/preview/{job_id}"
    return payload


@router.get("/3d/download/{job_id}")
async def download_reconstruction(job_id: str):
    status = job_status.get(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if status.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job not completed")

    output_path = status.get("output_path")
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Output file not found")

    filename = status.get("filename", f"reconstruction_{job_id}.stl")
    return FileResponse(output_path, media_type="application/octet-stream", filename=filename)


@router.get("/3d/preview/{job_id}")
async def preview_reconstruction(job_id: str):
    status = job_status.get(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if status.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job not completed")

    preview_path = status.get("preview_path")
    if not preview_path or not os.path.exists(preview_path):
        raise HTTPException(status_code=404, detail="Preview file not found")

    filename = status.get("preview_filename", f"reconstruct_{job_id}.glb")
    return FileResponse(preview_path, media_type="model/gltf-binary", filename=filename)


async def process_reconstruction_job(
    job_id: str,
    input_path: str,
    model: str,
    target_height_mm: float,
    output_format: str,
    do_repair: bool,
    decimate_ratio: float | None,
    remove_bg: bool,
) -> None:
    subject_path: str | None = None
    depth_map_path: str | None = None
    raw_mesh_path: str | None = None
    output_path: str | None = None
    preview_path: str | None = None

    try:
        job_status[job_id]["progress"] = 10

        if remove_bg:
            subject_path = remove_background(input_path)
        else:
            fd, copied = tempfile.mkstemp(suffix=Path(input_path).suffix or ".png", prefix="subject_")
            os.close(fd)
            shutil.copy2(input_path, copied)
            subject_path = copied

        job_status[job_id]["progress"] = 30
        depth_map_path = await estimate_depth(subject_path)

        job_status[job_id]["progress"] = 55
        if model == "sf3d":
            raw_mesh_path = await reconstruct_mesh_sf3d(subject_path, depth_map_path)
        else:
            raw_mesh_path = await reconstruct_mesh_triposr(subject_path)

        mesh = trimesh.load(raw_mesh_path, force="mesh")
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        job_status[job_id]["progress"] = 72
        if do_repair:
            mesh = repair_mesh(mesh)

        job_status[job_id]["progress"] = 84
        if decimate_ratio is not None and decimate_ratio < 1.0:
            mesh = decimate_mesh(mesh, float(decimate_ratio))

        job_status[job_id]["progress"] = 92
        # Always emit GLB preview for frontend rendering, regardless of final download format.
        preview_path = scale_and_export(mesh.copy(), target_height_mm, "glb")
        output_path = preview_path if output_format == "glb" else scale_and_export(mesh, target_height_mm, output_format)

        job_status[job_id].update(
            {
                "status": "completed",
                "progress": 100,
                "output_path": output_path,
                "filename": f"reconstruct_{job_id}.{output_format}",
                "preview_path": preview_path,
                "preview_filename": f"reconstruct_{job_id}.glb",
            }
        )
    except Exception as exc:
        logger.error("Reconstruction job %s failed: %s", job_id, exc, exc_info=True)
        job_status[job_id] = {"status": "failed", "error": str(exc), "progress": 100}
    finally:
        _safe_unlink(input_path)
        if subject_path and subject_path != input_path:
            _safe_unlink(subject_path)
        _safe_unlink(depth_map_path)
        _safe_unlink(raw_mesh_path)
