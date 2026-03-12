from __future__ import annotations

from typing import Any

import trimesh

from app.tabletop.parametric import ModelCategory, ParametricModelGenerator, Scale


class CharacterCustomizer:
    def __init__(self) -> None:
        self._generator = ParametricModelGenerator()

    def customize_character(self, choices: dict[str, Any], scale: float = 32.0) -> trimesh.Trimesh:
        mesh = self._generator.generate_model(
            ModelCategory.HUMAN,
            {
                "scale": choices.get("scale", Scale.STANDARD.value),
            },
        )

        weapon = choices.get("weapon", "none")
        if weapon != "none":
            mesh = trimesh.util.concatenate([mesh, self._weapon_mesh(weapon)])

        z_span = float(mesh.bounds[1][2] - mesh.bounds[0][2])
        if z_span > 0:
            mesh.apply_scale(scale / z_span)
        mesh.apply_translation([0.0, 0.0, -float(mesh.bounds[0][2])])
        return mesh

    def _weapon_mesh(self, weapon: str) -> trimesh.Trimesh:
        if weapon == "staff":
            obj = trimesh.primitives.Cylinder(radius=0.7, height=20.0)
            obj.apply_translation([6.0, 0.0, 12.0])
            return obj
        if weapon == "shield":
            obj = trimesh.primitives.Cylinder(radius=4.0, height=1.5)
            obj.apply_translation([6.0, 0.0, 12.0])
            obj.apply_transform(trimesh.transformations.rotation_matrix(1.57, [0, 1, 0]))
            return obj
        # sword default
        blade = trimesh.primitives.Box(extents=[1.0, 2.0, 14.0])
        blade.apply_translation([6.0, 0.0, 15.0])
        return blade
