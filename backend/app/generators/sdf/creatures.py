from __future__ import annotations

from typing import Any, Callable

import numpy as np
import trimesh

from .core import SDFConfig, SDFGenerator


class CreatureGenerator:
    """Procedural creature generator built on composable SDF fields."""

    def __init__(self) -> None:
        self.sdf = SDFGenerator()
        self.config = SDFConfig()
        self.archetypes: dict[str, Callable[[dict[str, Any]], Callable[[np.ndarray], float]]] = {
            "slime": self._create_slime,
            "beholder": self._create_beholder,
            "dragon": self._create_dragon,
            "demon_hound": self._create_demon_hound,
            "tentacle_horror": self._create_tentacle_horror,
            "spider": self._create_spider,
            "wolf": self._create_wolf,
            "elemental": self._create_elemental,
            "golem": self._create_golem,
            "undead": self._create_undead,
        }

    def generate_creature(
        self,
        species: str,
        params: dict[str, Any],
        config: SDFConfig | None = None,
    ) -> trimesh.Trimesh:
        if species not in self.archetypes:
            raise ValueError(f"Unknown species: {species}")

        sdf_func = self.archetypes[species](params)
        mesh = self.sdf.to_mesh(sdf_func, config or self.config)

        target_height = float(params.get("height", 50.0))
        current_height = float(mesh.bounds[1][2] - mesh.bounds[0][2])
        if current_height > 1e-6:
            mesh.apply_scale(target_height / current_height)

        mesh.apply_translation([0.0, 0.0, -mesh.bounds[0][2]])
        return mesh

    def _create_slime(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.0))
        blob_count = int(params.get("blob_count", 5))
        body = self.sdf.sphere((0, 0, size * 0.55), size)

        for i in range(max(1, blob_count)):
            angle = (i / max(1, blob_count)) * 2.0 * np.pi
            lobe = self.sdf.sphere((np.cos(angle) * size * 0.6, np.sin(angle) * size * 0.6, size * 0.2), size * 0.3)
            body = self.sdf.smooth_union(body, lobe, 0.25)

        return body

    def _create_beholder(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.0))
        eye_count = int(params.get("eye_count", 10))
        body = self.sdf.sphere((0, 0, size), size)
        main_eye = self.sdf.sphere((0, 0, size * 1.8), size * 0.25)
        body = self.sdf.smooth_union(body, main_eye, 0.15)

        for i in range(max(1, eye_count)):
            angle = (i / max(1, eye_count)) * 2.0 * np.pi
            end = (np.cos(angle) * size * 1.3, np.sin(angle) * size * 1.3, size * 1.4)
            stalk = self.sdf.capsule((0, 0, size), end, size * 0.1)
            eye = self.sdf.sphere(end, size * 0.12)
            body = self.sdf.smooth_union(body, self.sdf.smooth_union(stalk, eye, 0.08), 0.2)

        return body

    def _create_dragon(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.4))
        wing_span = float(params.get("wing_span", 2.0))

        body = self.sdf.capsule((-size * 0.6, 0, size * 0.2), (size * 0.6, 0, size * 0.35), size * 0.35)
        neck = self.sdf.capsule((size * 0.5, 0, size * 0.4), (size * 0.95, 0, size * 0.95), size * 0.15)
        head = self.sdf.sphere((size * 1.05, 0, size * 1.05), size * 0.2)
        tail = self.sdf.capsule((-size * 0.8, 0, 0.1), (-size * 1.5, 0, 0.3), size * 0.12)
        body = self.sdf.smooth_union(body, neck, 0.2)
        body = self.sdf.smooth_union(body, head, 0.12)
        body = self.sdf.smooth_union(body, tail, 0.15)

        for sign in (-1.0, 1.0):
            wing = self.sdf.box((0, sign * wing_span * 0.35, size * 0.55), (size * 0.9, wing_span * 0.55, size * 0.08))
            body = self.sdf.smooth_union(body, wing, 0.25)

        for sign in (-1.0, 1.0):
            for x in (-size * 0.4, size * 0.4):
                leg = self.sdf.capsule((x, sign * size * 0.15, size * 0.1), (x, sign * size * 0.15, -size * 0.45), size * 0.12)
                body = self.sdf.smooth_union(body, leg, 0.12)

        return body

    def _create_demon_hound(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.0))
        body = self.sdf.capsule((-size * 0.35, 0, size * 0.2), (size * 0.4, 0, size * 0.2), size * 0.32)
        head = self.sdf.sphere((size * 0.6, 0, size * 0.45), size * 0.25)
        snout = self.sdf.capsule((size * 0.75, 0, size * 0.45), (size, 0, size * 0.4), size * 0.1)
        tail = self.sdf.capsule((-size * 0.55, 0, size * 0.2), (-size * 0.9, 0, size * 0.4), size * 0.08)
        body = self.sdf.smooth_union(body, head, 0.18)
        body = self.sdf.smooth_union(body, snout, 0.12)
        body = self.sdf.smooth_union(body, tail, 0.1)

        for sign in (-1.0, 1.0):
            for x in (-size * 0.3, size * 0.3):
                leg = self.sdf.capsule((x, sign * size * 0.18, 0.0), (x, sign * size * 0.18, -size * 0.55), size * 0.1)
                body = self.sdf.smooth_union(body, leg, 0.12)

        return body

    def _create_tentacle_horror(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.0))
        tentacle_count = int(params.get("tentacle_count", 8))
        body = self.sdf.sphere((0, 0, size * 0.5), size * 0.85)

        for i in range(max(1, tentacle_count)):
            angle = (i / max(1, tentacle_count)) * 2.0 * np.pi
            a = (np.cos(angle) * size * 0.4, np.sin(angle) * size * 0.4, 0.0)
            b = (np.cos(angle) * size * 1.2, np.sin(angle) * size * 1.2, size * 0.8)
            tentacle = self.sdf.capsule(a, b, size * 0.1)
            body = self.sdf.smooth_union(body, tentacle, 0.2)

        return body

    def _create_spider(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.0))
        body = self.sdf.smooth_union(
            self.sdf.sphere((-size * 0.25, 0, size * 0.2), size * 0.45),
            self.sdf.sphere((size * 0.15, 0, size * 0.35), size * 0.35),
            0.2,
        )

        for i in range(8):
            angle = (i / 8.0) * 2.0 * np.pi
            elbow = (np.cos(angle) * size * 0.6, np.sin(angle) * size * 0.6, size * 0.1)
            foot = (np.cos(angle) * size * 1.0, np.sin(angle) * size * 1.0, -size * 0.25)
            leg = self.sdf.smooth_union(
                self.sdf.capsule((0, 0, size * 0.2), elbow, size * 0.08),
                self.sdf.capsule(elbow, foot, size * 0.06),
                0.1,
            )
            body = self.sdf.smooth_union(body, leg, 0.15)

        return body

    def _create_wolf(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        return self._create_demon_hound(params)

    def _create_elemental(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.0))
        element = str(params.get("element", "fire"))

        if element == "earth":
            body = self.sdf.sphere((0, 0, size), size)
            for i in range(10):
                angle = (i / 10.0) * 2.0 * np.pi
                rock = self.sdf.sphere((np.cos(angle) * size * 0.8, np.sin(angle) * size * 0.8, size), size * 0.2)
                body = self.sdf.smooth_union(body, rock, 0.15)
            return body

        if element == "air":
            core = self.sdf.sphere((0, 0, size), size * 0.6)
            for i in range(5):
                ring = self.sdf.torus((0, 0, size * (0.5 + i * 0.15)), size * (0.4 + i * 0.08), size * 0.08)
                core = self.sdf.smooth_union(core, ring, 0.18)
            return core

        if element == "water":
            body = self.sdf.sphere((0, 0, size), size)
            for i in range(6):
                angle = (i / 6.0) * 2.0 * np.pi
                wave = self.sdf.capsule((0, 0, size * 0.6), (np.cos(angle) * size, np.sin(angle) * size, size * 1.3), size * 0.1)
                body = self.sdf.smooth_union(body, wave, 0.2)
            return body

        flame = self.sdf.cone((0, 0, size), size * 2.0, size * 0.55, 0.02)
        for i in range(5):
            angle = (i / 5.0) * 2.0 * np.pi
            lick = self.sdf.capsule((0, 0, size * 0.8), (np.cos(angle) * size * 0.8, np.sin(angle) * size * 0.8, size * 1.7), size * 0.08)
            flame = self.sdf.smooth_union(flame, lick, 0.2)
        return flame

    def _create_golem(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.0))
        body = self.sdf.box((0, 0, size), (size * 1.2, size * 0.9, size * 1.1))
        head = self.sdf.box((0, 0, size * 1.75), (size * 0.6, size * 0.5, size * 0.5))
        arm_l = self.sdf.capsule((-size * 0.8, 0, size * 1.0), (-size * 1.1, 0, size * 0.4), size * 0.2)
        arm_r = self.sdf.capsule((size * 0.8, 0, size * 1.0), (size * 1.1, 0, size * 0.4), size * 0.2)
        leg_l = self.sdf.capsule((-size * 0.35, 0, size * 0.2), (-size * 0.35, 0, -size * 0.9), size * 0.2)
        leg_r = self.sdf.capsule((size * 0.35, 0, size * 0.2), (size * 0.35, 0, -size * 0.9), size * 0.2)

        body = self.sdf.smooth_union(body, head, 0.15)
        body = self.sdf.smooth_union(body, arm_l, 0.1)
        body = self.sdf.smooth_union(body, arm_r, 0.1)
        body = self.sdf.smooth_union(body, leg_l, 0.1)
        body = self.sdf.smooth_union(body, leg_r, 0.1)
        return body

    def _create_undead(self, params: dict[str, Any]) -> Callable[[np.ndarray], float]:
        size = float(params.get("size", 1.0))
        body = self.sdf.capsule((0, 0, size * 0.4), (0, 0, size * 1.2), size * 0.18)
        skull = self.sdf.sphere((0, 0, size * 1.45), size * 0.24)
        arm_l = self.sdf.capsule((-size * 0.3, 0, size * 0.9), (-size * 0.65, 0, size * 0.35), size * 0.08)
        arm_r = self.sdf.capsule((size * 0.3, 0, size * 0.9), (size * 0.65, 0, size * 0.35), size * 0.08)
        leg_l = self.sdf.capsule((-size * 0.2, 0, 0), (-size * 0.2, 0, -size * 0.7), size * 0.1)
        leg_r = self.sdf.capsule((size * 0.2, 0, 0), (size * 0.2, 0, -size * 0.7), size * 0.1)

        body = self.sdf.smooth_union(body, skull, 0.12)
        body = self.sdf.smooth_union(body, arm_l, 0.08)
        body = self.sdf.smooth_union(body, arm_r, 0.08)
        body = self.sdf.smooth_union(body, leg_l, 0.08)
        body = self.sdf.smooth_union(body, leg_r, 0.08)
        return body
