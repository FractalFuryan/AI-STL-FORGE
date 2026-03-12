from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from app.ai.statue_pipeline import StatuePipeline
from app.routes.reconstruct import _validate_upload, job_status

router = APIRouter(prefix="/api/statue", tags=["AI Statue"])


def get_pipeline() -> StatuePipeline:
    return StatuePipeline()


@router.post("/generate")
async def generate_statue(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    preset: str = Form("balanced"),
    model: str = Form("auto"),
    base_type: str = Form("none"),
    target_height_mm: float = Form(120.0),
    decimate_ratio: float = Form(0.6),
) -> dict[str, str]:
    if preset not in {"fast", "balanced", "high"}:
        raise HTTPException(status_code=400, detail="Preset must be 'fast', 'balanced', or 'high'")
    if model not in {"auto", "sf3d", "triposr"}:
        raise HTTPException(status_code=400, detail="Model must be 'auto', 'sf3d', or 'triposr'")
    if base_type not in {"none", "pedestal", "miniature"}:
        raise HTTPException(status_code=400, detail="base_type must be 'none', 'pedestal', or 'miniature'")
    if target_height_mm <= 0:
        raise HTTPException(status_code=400, detail="target_height_mm must be greater than 0")
    if not (0.1 <= decimate_ratio <= 1.0):
        raise HTTPException(status_code=400, detail="decimate_ratio must be between 0.1 and 1.0")

    content = await image.read()
    _validate_upload(image, content)

    suffix = Path(image.filename or "upload.png").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        suffix = ".png"

    job_id = str(uuid.uuid4())
    fd, input_path = tempfile.mkstemp(suffix=suffix, prefix=f"statue_input_{job_id}_")
    os.close(fd)

    with open(input_path, "wb") as handle:
        handle.write(content)

    job_status[job_id] = {
        "status": "processing",
        "progress": 1,
        "mode": "statue",
        "preset": preset,
        "model": model,
        "base_type": base_type,
    }

    background_tasks.add_task(
        process_statue,
        job_id,
        input_path,
        preset,
        model,
        base_type,
        target_height_mm,
        decimate_ratio,
    )

    return {"job_id": job_id, "status": "processing"}


async def process_statue(
    job_id: str,
    image_path: str,
    preset: str,
    model: str,
    base_type: str,
    target_height_mm: float,
    decimate_ratio: float,
) -> None:
    pipeline = get_pipeline()

    try:
        job_status[job_id]["progress"] = 15
        _mesh, stl_path, glb_path = await pipeline.run(
            image_path=image_path,
            preset=preset,
            model=model,
            target_height_mm=target_height_mm,
            decimate_ratio=decimate_ratio,
            base_type=base_type,
        )

        job_status[job_id] = {
            "status": "completed",
            "progress": 100,
            "mode": "statue",
            "base_type": base_type,
            "output_path": stl_path,
            "filename": f"statue_{job_id}.stl",
            "preview_path": glb_path,
            "preview_filename": f"statue_{job_id}.glb",
            "download_url": f"/api/reconstruct/3d/download/{job_id}",
            "preview_url": f"/api/reconstruct/3d/preview/{job_id}",
        }
    except Exception as exc:
        job_status[job_id] = {
            "status": "failed",
            "progress": 100,
            "mode": "statue",
            "error": str(exc),
        }
