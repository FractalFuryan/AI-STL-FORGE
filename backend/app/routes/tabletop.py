from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError

from app.models import TabletopCharacterRequest, TabletopKitRequest, TabletopParametricRequest
from app.tabletop.character import CharacterCustomizer
from app.tabletop.modular import ModularKitSystem
from app.tabletop.parametric import ModelCategory, ParametricModelGenerator
from app.tabletop.reconstruction import MultiViewReconstructor

router = APIRouter(prefix="/api/tabletop", tags=["tabletop"])

_reconstructor = MultiViewReconstructor()
_parametric = ParametricModelGenerator()
_modular = ModularKitSystem()
_character = CharacterCustomizer()


def _load_image(contents: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(contents)) as img:
            img.load()
            return img.convert("RGB")
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise HTTPException(status_code=400, detail="Invalid image for tabletop reconstruction") from exc


@router.post("/parametric/generate")
async def generate_parametric(payload: TabletopParametricRequest) -> Response:
    category = ModelCategory(payload.category)
    mesh = _parametric.generate_model(category, payload.params)
    stl = mesh.export(file_type="stl")
    return Response(
        content=stl,
        media_type="model/stl",
        headers={"Content-Disposition": 'attachment; filename="tabletop_parametric.stl"'},
    )


@router.post("/modular/kit")
async def create_modular_kit(payload: TabletopKitRequest) -> Response:
    pieces = _modular.create_kit(payload.kit_type, payload.num_pieces, payload.variation)

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for idx, piece in enumerate(pieces, start=1):
            zf.writestr(f"piece_{idx}.stl", piece.export(file_type="stl"))

    archive.seek(0)
    return Response(
        content=archive.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="tabletop_kit.zip"'},
    )


@router.post("/character/customize")
async def customize_character(payload: TabletopCharacterRequest) -> Response:
    mesh = _character.customize_character(payload.choices, payload.scale)
    stl = mesh.export(file_type="stl")
    return Response(
        content=stl,
        media_type="model/stl",
        headers={"Content-Disposition": 'attachment; filename="tabletop_character.stl"'},
    )


@router.post("/reconstruct")
async def reconstruct_model(
    front: UploadFile = File(...),
    side: UploadFile = File(...),
    top: UploadFile = File(...),
    back: UploadFile | None = File(default=None),
) -> Response:
    front_img = _load_image(await front.read())
    side_img = _load_image(await side.read())
    top_img = _load_image(await top.read())
    back_img = _load_image(await back.read()) if back is not None else None

    try:
        mesh = await _reconstructor.reconstruct_from_views(front_img, side_img, top_img, back_img)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stl = mesh.export(file_type="stl")
    return Response(
        content=stl,
        media_type="model/stl",
        headers={"Content-Disposition": 'attachment; filename="tabletop_reconstruction.stl"'},
    )
