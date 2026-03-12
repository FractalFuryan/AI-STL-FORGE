from __future__ import annotations

import logging
import os
import tempfile

import trimesh

logger = logging.getLogger(__name__)


def scale_and_export(mesh: trimesh.Trimesh, target_height_mm: float, fmt: str = "stl") -> str:
    """Scale to target height, align to build plate, and export."""
    bounds = mesh.bounds
    current_height = float(bounds[1][2] - bounds[0][2])

    if current_height > 1e-6:
        scale_factor = target_height_mm / current_height
        mesh.apply_scale(scale_factor)

    min_z = float(mesh.bounds[0][2])
    mesh.apply_translation([0.0, 0.0, -min_z])

    center_x = float((mesh.bounds[0][0] + mesh.bounds[1][0]) / 2)
    center_y = float((mesh.bounds[0][1] + mesh.bounds[1][1]) / 2)
    mesh.apply_translation([-center_x, -center_y, 0.0])

    suffix = f".{fmt}"
    fd, out_path = tempfile.mkstemp(suffix=suffix, prefix="reconstruct_")
    os.close(fd)

    if fmt == "stl":
        mesh.export(out_path, file_type="stl")
    elif fmt == "glb":
        mesh.export(out_path, file_type="glb")
    else:
        raise ValueError(f"Unsupported format: {fmt}")

    logger.info("Exported reconstruction to %s", out_path)
    return out_path
