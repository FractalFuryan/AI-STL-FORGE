from __future__ import annotations

from typing import Any, Callable

import numpy as np

from app.generators.sdf.busts.classical import ClassicalBust
from app.generators.sdf.busts.fantasy import FantasyBust
from app.generators.sdf.core import SDFGenerator


class BustFactory:
    def __init__(self) -> None:
        sdf = SDFGenerator()
        self.generators = {
            "classical": ClassicalBust(sdf),
            "fantasy": FantasyBust(sdf),
            # Aliases that map to currently implemented backbones.
            "realistic": ClassicalBust(sdf),
            "heroic": ClassicalBust(sdf),
            "villainous": FantasyBust(sdf),
            "gothic": FantasyBust(sdf),
            "anime": ClassicalBust(sdf),
            "cartoon": ClassicalBust(sdf),
            "alien": FantasyBust(sdf),
            "robot": ClassicalBust(sdf),
            "sci_fi": ClassicalBust(sdf),
            "steampunk": FantasyBust(sdf),
        }

    def list_styles(self) -> list[str]:
        return list(self.generators.keys())

    def list_races(self) -> list[str]:
        return ["human", "elf", "dwarf", "orc"]

    def generate(self, style: str, params: dict[str, Any]) -> Callable:
        if style not in self.generators:
            raise ValueError(f"Unknown style: {style}")
        return self.generators[style].generate(params)

    def generate_random(self, style: str, seed: int | None = None) -> Callable:
        if seed is not None:
            np.random.seed(seed)

        params: dict[str, Any] = {
            "size": float(np.random.uniform(0.85, 1.2)),
            "include_base": bool(np.random.choice([True, False])),
        }

        if style in {"fantasy", "villainous", "gothic", "alien", "steampunk"}:
            params["race"] = str(np.random.choice(["human", "elf", "dwarf", "orc"]))
            params["has_helmet"] = bool(np.random.choice([True, False]))
            params["has_crown"] = bool(np.random.choice([True, False]))
            params["has_beard"] = bool(np.random.choice([True, False]))

        return self.generate(style, params)
