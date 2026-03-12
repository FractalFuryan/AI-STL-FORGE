from __future__ import annotations

from typing import Callable

import trimesh


class ModularKitSystem:
    def __init__(self) -> None:
        self.kits: dict[str, Callable[[float], trimesh.Trimesh]] = {
            "floor": self._create_floor_tile,
            "wall": self._create_wall_piece,
            "corner": self._create_corner_piece,
            "pillar": self._create_pillar_piece,
            "door": self._create_door_piece,
        }

    def create_kit(self, kit_type: str, num_pieces: int = 10, variation: float = 0.3) -> list[trimesh.Trimesh]:
        if kit_type != "dungeon":
            raise ValueError("Currently only 'dungeon' modular kits are available")

        order = ["floor", "wall", "corner", "pillar", "door"]
        pieces: list[trimesh.Trimesh] = []
        for i in range(max(1, min(num_pieces, 50))):
            key = order[i % len(order)]
            pieces.append(self.kits[key](variation))
        return pieces

    def _create_floor_tile(self, variation: float) -> trimesh.Trimesh:
        tile = trimesh.primitives.Box(extents=[50.0, 50.0, 4.0])
        tile.apply_translation([0.0, 0.0, 2.0])
        bump = trimesh.primitives.Cylinder(radius=2.2, height=4.0)
        bump.apply_translation([20.0, 0.0, 2.0])
        if variation > 0.4:
            bump2 = bump.copy()
            bump2.apply_translation([-40.0, 0.0, 0.0])
            return trimesh.util.concatenate([tile, bump, bump2])
        return trimesh.util.concatenate([tile, bump])

    def _create_wall_piece(self, variation: float) -> trimesh.Trimesh:
        wall = trimesh.primitives.Box(extents=[50.0, 5.0, 38.0])
        wall.apply_translation([0.0, 0.0, 19.0])
        braces = []
        if variation < 0.3:
            return wall
        brace_l = trimesh.primitives.Box(extents=[14.0, 5.0, 38.0])
        brace_l.apply_translation([-18.0, 0.0, 19.0])
        brace_r = brace_l.copy()
        brace_r.apply_translation([36.0, 0.0, 0.0])
        lintel = trimesh.primitives.Box(extents=[20.0, 5.0, 10.0])
        lintel.apply_translation([0.0, 0.0, 33.0])
        braces.extend([brace_l, brace_r, lintel])
        return trimesh.util.concatenate([wall, *braces])

    def _create_corner_piece(self, _variation: float) -> trimesh.Trimesh:
        a = trimesh.primitives.Box(extents=[25.0, 5.0, 38.0])
        a.apply_translation([12.5, 0.0, 19.0])
        b = trimesh.primitives.Box(extents=[5.0, 25.0, 38.0])
        b.apply_translation([0.0, 12.5, 19.0])
        return trimesh.util.concatenate([a, b])

    def _create_pillar_piece(self, _variation: float) -> trimesh.Trimesh:
        pillar = trimesh.primitives.Cylinder(radius=6.0, height=40.0)
        pillar.apply_translation([0.0, 0.0, 20.0])
        base = trimesh.primitives.Cylinder(radius=9.0, height=4.0)
        base.apply_translation([0.0, 0.0, 2.0])
        return trimesh.util.concatenate([pillar, base])

    def _create_door_piece(self, _variation: float) -> trimesh.Trimesh:
        side_l = trimesh.primitives.Box(extents=[14.0, 5.0, 38.0])
        side_l.apply_translation([-18.0, 0.0, 19.0])
        side_r = side_l.copy()
        side_r.apply_translation([36.0, 0.0, 0.0])
        lintel = trimesh.primitives.Box(extents=[22.0, 5.0, 10.0])
        lintel.apply_translation([0.0, 0.0, 33.0])
        return trimesh.util.concatenate([side_l, side_r, lintel])
