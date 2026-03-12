from __future__ import annotations

import logging

import trimesh

logger = logging.getLogger(__name__)


def repair_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Run a conservative printability repair pass."""
    original_faces = len(mesh.faces)

    try:
        mesh.remove_duplicate_faces()
        mesh.remove_degenerate_faces()
    except Exception:
        pass

    try:
        if not mesh.is_watertight:
            mesh.fill_holes()
    except Exception:
        pass

    try:
        if not mesh.is_winding_consistent:
            mesh.fix_normals()
    except Exception:
        pass

    try:
        mesh.remove_unreferenced_vertices()
    except Exception:
        pass

    logger.info("Repair complete: %s -> %s faces", original_faces, len(mesh.faces))
    return mesh
