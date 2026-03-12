from __future__ import annotations

from typing import Any, Callable

from .base import BustBase


class ClassicalBust(BustBase):
    def generate(self, params: dict[str, Any]) -> Callable:
        size = float(params.get("size", 1.0))
        head = self.sdf.sphere((0.0, 0.0, size * 1.3), size * 0.45)
        neck = self.create_neck(size)
        chest = self.create_chest(size, width=0.55)

        bust = self.sdf.smooth_union(head, neck, 0.2)
        bust = self.sdf.smooth_union(bust, chest, 0.3)

        if bool(params.get("include_drapery", True)):
            drape = self.sdf.capsule((-size * 0.4, -size * 0.1, size * 0.4), (size * 0.4, -size * 0.1, size * 0.4), size * 0.15)
            bust = self.sdf.smooth_union(bust, drape, 0.2)

        nose = self.sdf.cone((0.0, size * 0.1, size * 1.4), size * 0.2, size * 0.1, 0.02)
        chin = self.sdf.sphere((0.0, -size * 0.15, size * 1.15), size * 0.11)
        bust = self.sdf.smooth_union(bust, nose, 0.08)
        bust = self.sdf.smooth_union(bust, chin, 0.12)

        bust = self.cut_plane(bust, z_level=0.0)
        return self.with_base(bust, params, size)
