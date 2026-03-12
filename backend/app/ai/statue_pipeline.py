from __future__ import annotations

import trimesh

from app.ai.depth import estimate_depth
from app.ai.reconstructor import reconstruct_mesh_sf3d, reconstruct_mesh_triposr, resolve_model
from app.ai.segmentation import segmenter
from app.mesh.bases.attach import attach_base
from app.mesh.bases.miniature import create_miniature_base
from app.mesh.bases.pedestal import create_pedestal
from app.mesh.export import scale_and_export
from app.mesh.remesh import decimate_mesh
from app.mesh.repair import repair_mesh


class StatuePipeline:
    async def run(
        self,
        image_path: str,
        preset: str = "balanced",
        model: str = "auto",
        target_height_mm: float = 120.0,
        decimate_ratio: float = 0.6,
        base_type: str = "none",
    ) -> tuple[trimesh.Trimesh, str, str]:
        # 1. Isolate subject.
        subject_path = segmenter.segment_subject(image_path)

        # 2. Estimate depth.
        depth_path = await estimate_depth(subject_path)

        # 3. Resolve effective reconstructor.
        model_name = resolve_model(model, preset)
        if model_name == "sf3d":
            raw_mesh_path = await self._run_sf3d(subject_path, depth_path)
        else:
            raw_mesh_path = await self._run_triposr(subject_path)

        mesh = trimesh.load(raw_mesh_path, force="mesh")
        if isinstance(mesh, trimesh.Scene):
            mesh = trimesh.util.concatenate(tuple(mesh.geometry.values()))

        # 4. Repair and simplify.
        mesh = repair_mesh(mesh)
        if decimate_ratio < 1.0:
            mesh = decimate_mesh(mesh, decimate_ratio)

        # 5. Optional base attachment.
        if base_type == "pedestal":
            mesh = attach_base(mesh, create_pedestal())
        elif base_type == "miniature":
            mesh = attach_base(mesh, create_miniature_base())

        # 6. Export both STL + GLB outputs.
        stl_path = scale_and_export(mesh.copy(), target_height_mm=target_height_mm, fmt="stl")
        glb_path = scale_and_export(mesh, target_height_mm=target_height_mm, fmt="glb")
        return mesh, stl_path, glb_path

    async def _run_sf3d(self, image_path: str, depth_path: str) -> str:
        return await reconstruct_mesh_sf3d(image_path, depth_path)

    async def _run_triposr(self, image_path: str) -> str:
        return await reconstruct_mesh_triposr(image_path)
