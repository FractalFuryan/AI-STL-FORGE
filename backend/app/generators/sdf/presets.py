from __future__ import annotations

CREATURE_PRESETS: dict[str, dict] = {
    "slime": {"size": 1.0, "blob_count": 5, "height": 35.0},
    "beholder": {"size": 1.2, "eye_count": 10, "height": 65.0},
    "dragon_whelp": {"size": 0.9, "wing_span": 1.6, "height": 70.0},
    "adult_dragon": {"size": 2.0, "wing_span": 3.0, "height": 120.0},
    "hell_hound": {"size": 1.0, "height": 45.0},
    "frost_wolf": {"size": 1.0, "height": 42.0},
    "cave_troll": {"size": 1.5, "height": 75.0},
    "forest_ent": {"size": 2.0, "height": 110.0},
    "mind_flayer": {"size": 1.0, "tentacle_count": 6, "height": 65.0},
}
