from __future__ import annotations

import random
from typing import Any


class CreatureMutator:
    """Generate families and hybrids from creature parameters."""

    def __init__(self, base_params: dict[str, Any]) -> None:
        self.base_params = dict(base_params)

    def mutate(self, mutation_rate: float = 0.3) -> dict[str, Any]:
        params = dict(self.base_params)

        if "size" in params and isinstance(params["size"], (float, int)):
            params["size"] = float(params["size"]) * random.uniform(0.7, 1.3)

        if "limb_count" in params and isinstance(params["limb_count"], int):
            params["limb_count"] = max(2, params["limb_count"] + random.randint(-2, 2))

        if random.random() < mutation_rate:
            params["has_spikes"] = random.choice([True, False])
        if random.random() < mutation_rate:
            params["has_wings"] = random.choice([True, False])
        if random.random() < mutation_rate:
            params["has_horns"] = random.choice([True, False])

        return params

    def generate_family(self, count: int = 5) -> list[dict[str, Any]]:
        return [self.base_params] + [self.mutate(0.3 + i * 0.1) for i in range(max(0, count - 1))]

    def hybridize(self, other: "CreatureMutator", blend: float = 0.5) -> dict[str, Any]:
        hybrid: dict[str, Any] = {}
        keys = set(self.base_params.keys()) | set(other.base_params.keys())

        for key in keys:
            if key in self.base_params and key in other.base_params:
                left = self.base_params[key]
                right = other.base_params[key]
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    hybrid[key] = (1.0 - blend) * float(left) + blend * float(right)
                else:
                    hybrid[key] = left if random.random() < blend else right
            elif key in self.base_params:
                hybrid[key] = self.base_params[key]
            else:
                hybrid[key] = other.base_params[key]

        return hybrid
