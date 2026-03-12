from __future__ import annotations

from typing import Optional

import numpy as np
import trimesh
from PIL import Image


class MultiViewReconstructor:
    """Simple orthographic silhouette reconstructor for tabletop MVP."""

    def _to_silhouette(self, image: Image.Image, resolution: int) -> np.ndarray:
        gray = image.convert("L").resize((resolution, resolution), Image.Resampling.BILINEAR)
        arr = np.asarray(gray, dtype=np.uint8)
        # Dark pixels are considered foreground.
        return arr < 180

    async def reconstruct_from_views(
        self,
        front_view: Image.Image,
        side_view: Image.Image,
        top_view: Image.Image,
        back_view: Optional[Image.Image] = None,
        resolution: int = 64,
    ) -> trimesh.Trimesh:
        front = self._to_silhouette(front_view, resolution)
        side = self._to_silhouette(side_view, resolution)
        top = self._to_silhouette(top_view, resolution)
        back = self._to_silhouette(back_view, resolution) if back_view is not None else None

        voxels = np.ones((resolution, resolution, resolution), dtype=bool)

        for x in range(resolution):
            for y in range(resolution):
                if not top[y, x]:
                    voxels[x, :, y] = False

        for x in range(resolution):
            for z in range(resolution):
                if not front[z, x]:
                    voxels[x, z, :] = False
                if back is not None and not back[z, x]:
                    voxels[x, z, :] = False

        for y in range(resolution):
            for z in range(resolution):
                if not side[z, y]:
                    voxels[:, z, y] = False

        if not np.any(voxels):
            raise ValueError("No 3D volume remained after silhouette carving")

        mesh = trimesh.voxel.VoxelGrid(voxels).as_boxes()
        mesh.remove_unreferenced_vertices()
        if len(mesh.faces) == 0:
            raise ValueError("Reconstruction produced an empty mesh")

        # Normalize height to standard tabletop miniature scale.
        z_span = float(mesh.bounds[1][2] - mesh.bounds[0][2])
        if z_span > 0:
            mesh.apply_scale(32.0 / z_span)
        z_min = float(mesh.bounds[0][2])
        mesh.apply_translation([0.0, 0.0, -z_min])
        return mesh
