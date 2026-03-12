from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response

from app.generators.sdf.busts.factory import BustFactory
from app.generators.sdf.core import SDFConfig, SDFGenerator

router = APIRouter(prefix="/api/busts", tags=["busts"])
factory = BustFactory()
mesh_gen = SDFGenerator()


@router.get("/styles")
async def list_styles() -> list[str]:
    return factory.list_styles()


@router.get("/races")
async def list_races() -> list[str]:
    return factory.list_races()


@router.get("/base-types")
async def list_base_types() -> list[str]:
    return ["head_only", "head_neck", "head_shoulders", "upper_chest", "full_bust", "heroic_bust"]


@router.post("/generate/{style}")
async def generate_bust(
    style: str,
    params: dict | None = Body(default=None),
    resolution: int = Query(96, ge=24, le=192),
    height: float = Query(80.0, ge=20.0, le=300.0),
) -> Response:
    if style not in factory.list_styles():
        raise HTTPException(status_code=404, detail=f"Unknown style: {style}")

    payload = params or {}
    sdf_func = factory.generate(style, payload)
    mesh = mesh_gen.to_mesh(sdf_func, SDFConfig(resolution=resolution, bounds=2.0))

    current_height = float(mesh.bounds[1][2] - mesh.bounds[0][2])
    if current_height > 1e-6:
        mesh.apply_scale(height / current_height)
    mesh.apply_translation([0.0, 0.0, -mesh.bounds[0][2]])

    return Response(
        content=mesh.export(file_type="stl"),
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{style}_bust.stl"'},
    )


@router.post("/random/{style}")
async def random_bust(
    style: str,
    seed: int | None = Query(default=None),
    resolution: int = Query(96, ge=24, le=192),
    height: float = Query(80.0, ge=20.0, le=300.0),
) -> Response:
    if style not in factory.list_styles():
        raise HTTPException(status_code=404, detail=f"Unknown style: {style}")

    sdf_func = factory.generate_random(style, seed)
    mesh = mesh_gen.to_mesh(sdf_func, SDFConfig(resolution=resolution, bounds=2.0))

    current_height = float(mesh.bounds[1][2] - mesh.bounds[0][2])
    if current_height > 1e-6:
        mesh.apply_scale(height / current_height)
    mesh.apply_translation([0.0, 0.0, -mesh.bounds[0][2]])

    suffix = seed if seed is not None else 0
    return Response(
        content=mesh.export(file_type="stl"),
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{style}_random_{suffix}.stl"'},
    )
