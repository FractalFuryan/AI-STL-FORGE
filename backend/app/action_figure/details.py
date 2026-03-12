from __future__ import annotations

import trimesh


class DetailGenerator:
    """Simple accessories and outfit add-ons for action figures."""

    def add_weapon(self, weapon_type: str, scale: float = 1.0) -> trimesh.Trimesh:
        if weapon_type == "sword":
            blade = trimesh.creation.box(extents=[4, 12, 72])
            blade.apply_translation([0, 0, 36])
            guard = trimesh.creation.box(extents=[22, 4, 4])
            guard.apply_translation([0, 0, 2])
            hilt = trimesh.creation.cylinder(radius=4, height=18, sections=16)
            hilt.apply_translation([0, 0, -8])
            weapon = trimesh.util.concatenate([blade, guard, hilt])
        elif weapon_type == "gun":
            body = trimesh.creation.box(extents=[16, 30, 18])
            body.apply_translation([0, 0, 6])
            barrel = trimesh.creation.cylinder(radius=3, height=44, sections=16)
            barrel.apply_translation([0, 0, 24])
            grip = trimesh.creation.box(extents=[10, 8, 18])
            grip.apply_translation([0, -10, -6])
            weapon = trimesh.util.concatenate([body, barrel, grip])
        else:
            weapon = trimesh.creation.box(extents=[8, 8, 24])

        weapon.apply_scale(scale)
        return weapon
