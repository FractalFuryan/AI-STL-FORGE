from __future__ import annotations

import logging

import trimesh

logger = logging.getLogger(__name__)


def decimate_mesh(mesh: trimesh.Trimesh, ratio: float = 0.6) -> trimesh.Trimesh:
    """Simplify mesh while preserving printable fidelity."""
    if ratio >= 1.0:
        return mesh

    target_faces = max(100, int(len(mesh.faces) * ratio))
    logger.info("Decimating mesh to %s faces", target_faces)

    try:
        simplified = mesh.simplify_quadric_decimation(face_count=target_faces)
        if simplified is not None and len(simplified.faces) > 0:
            return simplified
    except Exception as exc:
        logger.warning("Decimation unavailable/failure, returning original mesh: %s", exc)

    return mesh
