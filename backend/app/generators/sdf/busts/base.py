from __future__ import annotations

from typing import Any, Callable

from app.generators.sdf.core import SDFGenerator


class BustBase:
    def __init__(self, sdf: SDFGenerator) -> None:
        self.sdf = sdf

    def create_base(self, radius: float = 1.2, height: float = 0.3) -> Callable:
        base = self.sdf.cylinder((0.0, 0.0, 0.0), (0.0, 0.0, height), radius)
        rim = self.sdf.cylinder((0.0, 0.0, height * 0.8), (0.0, 0.0, height * 1.2), radius * 1.08)
        return self.sdf.smooth_union(base, rim, 0.05)

    def create_neck(self, size: float = 1.0) -> Callable:
        return self.sdf.capsule((0.0, 0.0, size * 0.6), (0.0, 0.0, size * 1.0), size * 0.18)

    def create_chest(self, size: float = 1.0, width: float = 0.55) -> Callable:
        return self.sdf.capsule((0.0, 0.0, 0.0), (0.0, 0.0, size * 0.7), size * width)

    def cut_plane(self, shape: Callable, z_level: float = 0.0) -> Callable:
        return self.sdf.cut_plane(shape, z_level)

    def with_base(self, bust: Callable, params: dict[str, Any], size: float) -> Callable:
        if not bool(params.get("include_base", True)):
            return bust
        base = self.create_base(radius=size * 0.82, height=size * 0.2)
        return self.sdf.union(bust, self.sdf.transform(base, translate=(0.0, 0.0, -size * 0.1)))
