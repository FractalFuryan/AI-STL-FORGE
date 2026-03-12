from __future__ import annotations

import trimesh


def create_miniature_base() -> trimesh.Trimesh:
    """Create a compact gaming miniature-style circular base."""
    base = trimesh.creation.cylinder(radius=12.5, height=3.0, sections=42)
    base.apply_translation([0.0, 0.0, 1.5])
    return base
