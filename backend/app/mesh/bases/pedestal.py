from __future__ import annotations

import trimesh


def create_pedestal() -> trimesh.Trimesh:
    """Create a simple round pedestal suitable for bust-style models."""
    pedestal = trimesh.creation.cylinder(radius=16.0, height=12.0, sections=48)
    pedestal.apply_translation([0.0, 0.0, 6.0])
    top_lip = trimesh.creation.cylinder(radius=18.0, height=2.0, sections=48)
    top_lip.apply_translation([0.0, 0.0, 11.0])
    return trimesh.util.concatenate([pedestal, top_lip])
