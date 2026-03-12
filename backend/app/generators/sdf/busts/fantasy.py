from __future__ import annotations

from typing import Any, Callable

from .base import BustBase


class FantasyBust(BustBase):
    def generate(self, params: dict[str, Any]) -> Callable:
        race = str(params.get("race", "human"))
        size = float(params.get("size", 1.0))

        if race == "elf":
            bust = self._elf(size)
        elif race == "dwarf":
            bust = self._dwarf(size)
        elif race == "orc":
            bust = self._orc(size)
        else:
            bust = self._human(size)

        if bool(params.get("has_helmet", False)):
            helmet = self.sdf.sphere((0.0, 0.1, size * 1.35), size * 0.5)
            face_cut = self.sdf.box((0.0, 0.08, size * 1.24), (size * 0.34, size * 0.2, size * 0.34))
            bust = self.sdf.smooth_union(bust, self.sdf.subtract(helmet, face_cut), 0.1)

        if bool(params.get("has_crown", False)):
            crown = self.sdf.torus((0.0, 0.0, size * 1.52), size * 0.3, size * 0.05)
            bust = self.sdf.smooth_union(bust, crown, 0.08)

        if bool(params.get("has_beard", False)) and race in {"human", "dwarf"}:
            beard = self.sdf.capsule((0.0, -size * 0.15, size * 1.0), (0.0, -size * 0.42, size * 0.6), size * 0.2)
            bust = self.sdf.smooth_union(bust, beard, 0.15)

        bust = self.cut_plane(bust, z_level=0.0)
        return self.with_base(bust, params, size)

    def _human(self, size: float) -> Callable:
        head = self.sdf.sphere((0.0, 0.0, size * 1.25), size * 0.45)
        neck = self.create_neck(size)
        chest = self.create_chest(size, width=0.50)
        return self.sdf.smooth_union(self.sdf.smooth_union(head, neck, 0.2), chest, 0.25)

    def _elf(self, size: float) -> Callable:
        base = self._human(size)
        ear_l = self.sdf.cone((-size * 0.35, size * 0.1, size * 1.4), size * 0.2, size * 0.1, 0.02)
        ear_r = self.sdf.cone((size * 0.35, size * 0.1, size * 1.4), size * 0.2, size * 0.1, 0.02)
        return self.sdf.smooth_union(self.sdf.smooth_union(base, ear_l, 0.1), ear_r, 0.1)

    def _dwarf(self, size: float) -> Callable:
        head = self.sdf.sphere((0.0, 0.0, size * 1.2), size * 0.45)
        neck = self.sdf.capsule((0.0, 0.0, size * 0.5), (0.0, 0.0, size * 0.9), size * 0.25)
        chest = self.sdf.capsule((0.0, 0.0, -size * 0.2), (0.0, 0.0, size * 0.5), size * 0.6)
        return self.sdf.smooth_union(self.sdf.smooth_union(head, neck, 0.2), chest, 0.3)

    def _orc(self, size: float) -> Callable:
        head = self.sdf.sphere((0.0, 0.0, size * 1.2), size * 0.5)
        jaw = self.sdf.sphere((0.0, -size * 0.15, size * 1.0), size * 0.35)
        neck = self.sdf.capsule((0.0, 0.0, size * 0.5), (0.0, 0.0, size * 0.9), size * 0.3)
        shoulder_l = self.sdf.sphere((-size * 0.5, 0.0, size * 0.3), size * 0.4)
        shoulder_r = self.sdf.sphere((size * 0.5, 0.0, size * 0.3), size * 0.4)

        bust = self.sdf.smooth_union(head, jaw, 0.3)
        bust = self.sdf.smooth_union(bust, neck, 0.25)
        bust = self.sdf.smooth_union(bust, shoulder_l, 0.2)
        bust = self.sdf.smooth_union(bust, shoulder_r, 0.2)

        tusk_l = self.sdf.cone((-size * 0.12, -size * 0.1, size * 1.05), size * 0.15, size * 0.08, 0.02)
        tusk_r = self.sdf.cone((size * 0.12, -size * 0.1, size * 1.05), size * 0.15, size * 0.08, 0.02)
        bust = self.sdf.smooth_union(bust, tusk_l, 0.08)
        bust = self.sdf.smooth_union(bust, tusk_r, 0.08)
        return bust
