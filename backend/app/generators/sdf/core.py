from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import trimesh


@dataclass
class SDFConfig:
    resolution: int = 64
    bounds: float = 2.0
    smoothness: float = 0.2
    detail_level: str = "standard"


class SDFGenerator:
    """Core SDF primitives and conversion to watertight meshes."""

    def __init__(self, config: SDFConfig | None = None) -> None:
        self.config = config or SDFConfig()

    @staticmethod
    def sphere(center: tuple[float, float, float], radius: float) -> Callable[[np.ndarray], float]:
        center_np = np.asarray(center, dtype=np.float64)

        def sdf(p: np.ndarray) -> float:
            return float(np.linalg.norm(p - center_np) - radius)

        return sdf

    @staticmethod
    def capsule(
        a: tuple[float, float, float],
        b: tuple[float, float, float],
        radius: float,
    ) -> Callable[[np.ndarray], float]:
        a_np = np.asarray(a, dtype=np.float64)
        b_np = np.asarray(b, dtype=np.float64)
        ba = b_np - a_np
        ba_dot = float(np.dot(ba, ba))

        def sdf(p: np.ndarray) -> float:
            pa = p - a_np
            if ba_dot <= 1e-10:
                return float(np.linalg.norm(pa) - radius)
            h = np.clip(np.dot(pa, ba) / ba_dot, 0.0, 1.0)
            return float(np.linalg.norm(pa - ba * h) - radius)

        return sdf

    @staticmethod
    def box(
        center: tuple[float, float, float],
        size: tuple[float, float, float],
    ) -> Callable[[np.ndarray], float]:
        center_np = np.asarray(center, dtype=np.float64)
        half = np.asarray(size, dtype=np.float64) / 2.0

        def sdf(p: np.ndarray) -> float:
            q = np.abs(p - center_np) - half
            return float(np.linalg.norm(np.maximum(q, 0.0)) + min(np.max(q), 0.0))

        return sdf

    @staticmethod
    def torus(center: tuple[float, float, float], r1: float, r2: float) -> Callable[[np.ndarray], float]:
        center_np = np.asarray(center, dtype=np.float64)

        def sdf(p: np.ndarray) -> float:
            q = p - center_np
            x = np.linalg.norm([q[0], q[2]]) - r1
            return float(np.sqrt(x * x + q[1] * q[1]) - r2)

        return sdf

    @staticmethod
    def cone(
        center: tuple[float, float, float],
        height: float,
        r1: float,
        r2: float,
    ) -> Callable[[np.ndarray], float]:
        center_np = np.asarray(center, dtype=np.float64)

        def sdf(p: np.ndarray) -> float:
            q = p - center_np
            h = max(height, 1e-6)
            d = np.sqrt(q[0] * q[0] + q[2] * q[2])
            t = np.clip((q[1] + h / 2.0) / h, 0.0, 1.0)
            r = r1 + (r2 - r1) * t
            return float(max(d - r, abs(q[1]) - h / 2.0))

        return sdf

    @staticmethod
    def cylinder(
        a: tuple[float, float, float],
        b: tuple[float, float, float],
        radius: float,
    ) -> Callable[[np.ndarray], float]:
        a_np = np.asarray(a, dtype=np.float64)
        b_np = np.asarray(b, dtype=np.float64)
        ba = b_np - a_np
        ba_dot = float(np.dot(ba, ba))

        def sdf(p: np.ndarray) -> float:
            pa = p - a_np
            if ba_dot <= 1e-10:
                return float(np.linalg.norm(pa) - radius)
            h = np.clip(np.dot(pa, ba) / ba_dot, 0.0, 1.0)
            radial = np.linalg.norm(pa - ba * h) - radius
            cap = max(h - 1.0, -h)
            return float(max(radial, cap))

        return sdf

    @staticmethod
    def union(a: Callable[[np.ndarray], float], b: Callable[[np.ndarray], float]) -> Callable[[np.ndarray], float]:
        def sdf(p: np.ndarray) -> float:
            return float(min(a(p), b(p)))

        return sdf

    @staticmethod
    def subtract(a: Callable[[np.ndarray], float], b: Callable[[np.ndarray], float]) -> Callable[[np.ndarray], float]:
        def sdf(p: np.ndarray) -> float:
            return float(max(a(p), -b(p)))

        return sdf

    @staticmethod
    def smooth_union(a: Callable[[np.ndarray], float], b: Callable[[np.ndarray], float], k: float = 0.2) -> Callable[[np.ndarray], float]:
        eps = max(k, 1e-6)

        def sdf(p: np.ndarray) -> float:
            d1 = a(p)
            d2 = b(p)
            h = np.clip(0.5 + 0.5 * (d2 - d1) / eps, 0.0, 1.0)
            return float((1.0 - h) * d2 + h * d1 - eps * h * (1.0 - h))

        return sdf

    @staticmethod
    def smooth_subtract(a: Callable[[np.ndarray], float], b: Callable[[np.ndarray], float], k: float = 0.2) -> Callable[[np.ndarray], float]:
        eps = max(k, 1e-6)

        def sdf(p: np.ndarray) -> float:
            d1 = a(p)
            d2 = -b(p)
            h = np.clip(0.5 + 0.5 * (d2 - d1) / eps, 0.0, 1.0)
            return float((1.0 - h) * d2 + h * d1 - eps * h * (1.0 - h))

        return sdf

    @staticmethod
    def intersect(a: Callable[[np.ndarray], float], b: Callable[[np.ndarray], float]) -> Callable[[np.ndarray], float]:
        def sdf(p: np.ndarray) -> float:
            return float(max(a(p), b(p)))

        return sdf

    @staticmethod
    def cut_plane(shape: Callable[[np.ndarray], float], z_level: float) -> Callable[[np.ndarray], float]:
        def sdf(p: np.ndarray) -> float:
            return float(max(shape(p), z_level - p[2]))

        return sdf

    @staticmethod
    def transform(
        shape: Callable[[np.ndarray], float],
        scale: tuple[float, float, float] = (1.0, 1.0, 1.0),
        translate: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> Callable[[np.ndarray], float]:
        s = np.asarray(scale, dtype=np.float64)
        t = np.asarray(translate, dtype=np.float64)
        min_scale = float(np.min(np.abs(s))) if np.all(np.abs(s) > 0) else 1.0

        def sdf(p: np.ndarray) -> float:
            p_inv = (p - t) / s
            return float(shape(p_inv) * min_scale)

        return sdf

    def to_mesh(self, sdf: Callable[[np.ndarray], float], config: SDFConfig | None = None) -> trimesh.Trimesh:
        cfg = config or self.config

        grid = np.linspace(-cfg.bounds, cfg.bounds, cfg.resolution, dtype=np.float32)
        xg, yg, zg = np.meshgrid(grid, grid, grid, indexing="ij")
        points = np.stack([xg.ravel(), yg.ravel(), zg.ravel()], axis=-1)

        field = np.empty(points.shape[0], dtype=np.float32)
        for i, point in enumerate(points):
            field[i] = sdf(point)

        voxels = (field.reshape((cfg.resolution, cfg.resolution, cfg.resolution)) <= 0.0).astype(np.uint8)
        if voxels.sum() == 0:
            return trimesh.creation.icosphere(subdivisions=2, radius=1.0)

        pitch = (2.0 * cfg.bounds) / cfg.resolution
        transform = np.eye(4)
        transform[0, 0] = pitch
        transform[1, 1] = pitch
        transform[2, 2] = pitch
        transform[:3, 3] = [-cfg.bounds, -cfg.bounds, -cfg.bounds]

        mesh = trimesh.voxel.VoxelGrid(voxels, transform=transform).as_boxes()
        mesh.merge_vertices()
        return mesh
