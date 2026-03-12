from __future__ import annotations

import io
import zipfile

import cv2
import numpy as np
import trimesh
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response

from app.action_figure.details import DetailGenerator
from app.action_figure.generator import ActionFigureGenerator

router = APIRouter(prefix="/api/action-figure", tags=["action-figure"])

generator = ActionFigureGenerator()
detail_gen = DetailGenerator()


def _decode_image(contents: bytes) -> np.ndarray:
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image data")
    return img


@router.post("/extract-pose")
async def extract_pose(image: UploadFile = File(...)) -> JSONResponse:
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Image is empty")

    img = _decode_image(contents)
    pose = await generator.extract_pose(img)
    return JSONResponse(content=pose)


@router.post("/generate")
async def generate_action_figure(
    image: UploadFile = File(...),
    style: str = Form("realistic"),
    scale: str = Form("1:6"),
    articulated: bool = Form(True),
) -> Response:
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Image is empty")

    img = _decode_image(contents)
    mesh = await generator.generate_from_image(img, style=style, scale=scale, articulated=articulated)
    stl = mesh.export(file_type="stl")

    safe_scale = scale.replace(":", "-")
    return Response(
        content=stl,
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="action_figure_{style}_{safe_scale}.stl"'},
    )


@router.post("/add-accessories")
async def add_accessories(
    stl_file: UploadFile = File(...),
    accessories: str = Form("[]"),
) -> Response:
    try:
        import json

        accessory_list = json.loads(accessories)
        if not isinstance(accessory_list, list):
            raise ValueError("accessories must be a list")
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid accessories payload: {exc}") from exc

    data = await stl_file.read()
    if not data:
        raise HTTPException(status_code=400, detail="STL file is empty")

    mesh = trimesh.load(io.BytesIO(data), file_type="stl")
    if isinstance(mesh, trimesh.Scene):
        mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

    for item in accessory_list:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "weapon":
            continue

        weapon_name = str(item.get("name", "sword"))
        weapon_scale = float(item.get("scale", 1.0))
        weapon = detail_gen.add_weapon(weapon_name, weapon_scale)
        weapon.apply_translation([40.0, 0.0, 80.0])
        mesh = trimesh.util.concatenate([mesh, weapon])

    output = mesh.export(file_type="stl")
    return Response(
        content=output,
        media_type="model/stl",
        headers={"Content-Disposition": 'attachment; filename="action_figure_accessories.stl"'},
    )
