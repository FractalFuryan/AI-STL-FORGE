from __future__ import annotations

import io
import json
import zipfile

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response

from app.models import CreatureHybridRequest
from app.generators.sdf.core import SDFConfig
from app.generators.sdf.creatures import CreatureGenerator
from app.generators.sdf.mutations import CreatureMutator
from app.generators.sdf.presets import CREATURE_PRESETS

router = APIRouter(prefix="/api/creatures", tags=["creatures"])
generator = CreatureGenerator()


@router.get("/species")
async def list_species() -> list[str]:
    return list(generator.archetypes.keys())


@router.get("/presets/{species}")
async def get_presets(species: str) -> dict[str, dict]:
    return {k: v for k, v in CREATURE_PRESETS.items() if species in k}


@router.post("/generate/{species}")
async def generate_creature(
    species: str,
    params: dict | None = Body(default=None),
    resolution: int = Query(56, ge=24, le=128),
) -> Response:
    if species not in generator.archetypes:
        raise HTTPException(status_code=404, detail=f"Unknown species: {species}")

    payload = params or CREATURE_PRESETS.get(species, {})
    config = SDFConfig(resolution=resolution)
    mesh = generator.generate_creature(species, payload, config)

    return Response(
        content=mesh.export(file_type="stl"),
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="{species}_creature.stl"'},
    )


@router.post("/mutate/{species}")
async def mutate_creature(
    species: str,
    base_params: dict = Body(...),
    count: int = Query(5, ge=1, le=20),
    mutation_rate: float = Query(0.3, ge=0.1, le=1.0),
) -> Response:
    if species not in generator.archetypes:
        raise HTTPException(status_code=404, detail=f"Unknown species: {species}")

    mutator = CreatureMutator(base_params)
    family = [base_params] + [mutator.mutate(mutation_rate) for _ in range(max(0, count - 1))]

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, params in enumerate(family, start=1):
            mesh = generator.generate_creature(species, params, SDFConfig(resolution=42))
            zf.writestr(f"{species}_variant_{idx}.stl", mesh.export(file_type="stl"))
            zf.writestr(f"{species}_variant_{idx}.json", json.dumps(params, indent=2))

    archive.seek(0)
    return Response(
        content=archive.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{species}_family.zip"'},
    )


@router.post("/hybrid")
async def hybrid_creatures(
    payload: CreatureHybridRequest,
) -> Response:
    species1 = payload.species1
    species2 = payload.species2
    if species1 not in generator.archetypes:
        raise HTTPException(status_code=404, detail=f"Unknown species: {species1}")
    if species2 not in generator.archetypes:
        raise HTTPException(status_code=404, detail=f"Unknown species: {species2}")

    hybrid_params = CreatureMutator(payload.params1).hybridize(CreatureMutator(payload.params2), payload.blend)
    mesh = generator.generate_creature(species1, hybrid_params, SDFConfig(resolution=56))

    return Response(
        content=mesh.export(file_type="stl"),
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="hybrid_{species1}_{species2}.stl"'},
    )
