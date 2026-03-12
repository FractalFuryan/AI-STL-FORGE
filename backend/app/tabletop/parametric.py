from __future__ import annotations

from enum import Enum
from typing import Any

import trimesh


class ModelCategory(str, Enum):
    HUMAN = "human"
    CREATURE = "creature"
    TERRAIN = "terrain"
    PROP = "prop"


class Scale(str, Enum):
    MICRO = "micro"
    STANDARD = "standard"
    HEROIC = "heroic"
    TERRAIN = "terrain"


class ParametricModelGenerator:
    def generate_model(self, category: ModelCategory, params: dict[str, Any]) -> trimesh.Trimesh:
        if category == ModelCategory.HUMAN:
            return self._create_humanoid(params)
        if category == ModelCategory.CREATURE:
            return self._create_creature(params)
        if category == ModelCategory.TERRAIN:
            return self._create_terrain(params)
        return self._create_prop(params)

    def _target_height(self, scale: Scale) -> float:
        mapping = {
            Scale.MICRO: 15.0,
            Scale.STANDARD: 32.0,
            Scale.HEROIC: 54.0,
            Scale.TERRAIN: 50.0,
        }
        return mapping[scale]

    def _normalize_height(self, mesh: trimesh.Trimesh, target_height: float) -> trimesh.Trimesh:
        z_span = float(mesh.bounds[1][2] - mesh.bounds[0][2])
        if z_span > 0:
            mesh.apply_scale(target_height / z_span)
        mesh.apply_translation([0.0, 0.0, -float(mesh.bounds[0][2])])
        return mesh

    def _create_humanoid(self, params: dict[str, Any]) -> trimesh.Trimesh:
        scale = Scale(params.get("scale", Scale.STANDARD))

        torso = trimesh.primitives.Capsule(radius=2.6, height=11.0)
        torso.apply_translation([0.0, 0.0, 10.0])

        head = trimesh.primitives.Sphere(radius=2.7)
        head.apply_translation([0.0, 0.0, 18.5])

        leg_l = trimesh.primitives.Cylinder(radius=1.5, height=10.0)
        leg_l.apply_translation([-1.3, 0.0, 5.0])
        leg_r = leg_l.copy()
        leg_r.apply_translation([2.6, 0.0, 0.0])

        arm_l = trimesh.primitives.Cylinder(radius=1.1, height=8.0)
        arm_l.apply_translation([-4.0, 0.0, 12.0])
        arm_l.apply_transform(trimesh.transformations.rotation_matrix(0.3, [0, 1, 0]))
        arm_r = arm_l.copy()
        arm_r.apply_translation([8.0, 0.0, 0.0])
        arm_r.apply_transform(trimesh.transformations.rotation_matrix(-0.6, [0, 0, 1]))

        base = trimesh.primitives.Cylinder(radius=8.0, height=2.0)
        base.apply_translation([0.0, 0.0, 1.0])

        mesh = trimesh.util.concatenate([torso, head, leg_l, leg_r, arm_l, arm_r, base])
        return self._normalize_height(mesh, self._target_height(scale))

    def _create_creature(self, params: dict[str, Any]) -> trimesh.Trimesh:
        scale = Scale(params.get("scale", Scale.STANDARD))

        body = trimesh.primitives.Icosahedron(radius=7.0)
        body.apply_scale([1.0, 0.7, 0.8])
        body.apply_translation([0.0, 0.0, 8.0])

        eye = trimesh.primitives.Sphere(radius=2.1)
        eye.apply_translation([4.0, 0.0, 11.0])

        stalk = trimesh.primitives.Cylinder(radius=0.6, height=6.0)
        stalk.apply_translation([6.5, 0.0, 13.5])
        stalk.apply_transform(trimesh.transformations.rotation_matrix(0.5, [0, 1, 0]))

        base = trimesh.primitives.Cylinder(radius=8.5, height=2.0)
        base.apply_translation([0.0, 0.0, 1.0])

        mesh = trimesh.util.concatenate([body, eye, stalk, base])
        return self._normalize_height(mesh, self._target_height(scale))

    def _create_terrain(self, params: dict[str, Any]) -> trimesh.Trimesh:
        size = float(params.get("tile_size", 50.0))
        height = float(params.get("height", 6.0))

        tile = trimesh.primitives.Box(extents=[size, size, height])
        tile.apply_translation([0.0, 0.0, height / 2])

        pillar = trimesh.primitives.Cylinder(radius=size * 0.12, height=height * 3.0)
        pillar.apply_translation([size * 0.2, size * 0.2, height * 1.5])

        mesh = trimesh.util.concatenate([tile, pillar])
        return self._normalize_height(mesh, self._target_height(Scale.TERRAIN))

    def _create_prop(self, params: dict[str, Any]) -> trimesh.Trimesh:
        prop_type = params.get("type", "barrel")
        if prop_type == "crate":
            mesh = trimesh.primitives.Box(extents=[12.0, 12.0, 12.0])
        else:
            mesh = trimesh.primitives.Cylinder(radius=5.5, height=10.0)
        mesh.apply_translation([0.0, 0.0, -float(mesh.bounds[0][2])])
        return mesh
