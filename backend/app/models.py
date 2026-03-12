from typing import Literal

from pydantic import BaseModel, Field


class GenerationParams(BaseModel):
    mode: Literal["heightmap", "lithophane", "emboss", "relief", "ai-depth", "cookie-cutter"] = "heightmap"
    preset: Literal["custom", "ender3_v3", "prusa_mk4", "bambu_a1_mini"] = "custom"
    max_height: float = Field(default=8.0, ge=0.5, le=40.0)
    base_thickness: float = Field(default=2.0, ge=0.5, le=20.0)
    gamma: float = Field(default=1.0, ge=0.2, le=3.0)
    smooth_sigma: float = Field(default=0.0, ge=0.0, le=5.0)
    resolution: int = Field(default=192, ge=32, le=512)
    target_width_mm: float = Field(default=100.0, ge=20.0, le=300.0)
    cutter_height: float = Field(default=10.0, ge=5.0, le=30.0)
    cutter_thickness: float = Field(default=2.0, ge=0.8, le=5.0)
    adaptive_remesh: bool = False


class TabletopParametricRequest(BaseModel):
    category: Literal["human", "creature", "terrain", "prop"] = "human"
    params: dict = Field(default_factory=dict)


class TabletopKitRequest(BaseModel):
    kit_type: Literal["dungeon"] = "dungeon"
    num_pieces: int = Field(default=10, ge=1, le=50)
    variation: float = Field(default=0.3, ge=0.0, le=1.0)


class TabletopCharacterRequest(BaseModel):
    choices: dict = Field(default_factory=dict)
    scale: float = Field(default=32.0, ge=10.0, le=120.0)


class CreatureHybridRequest(BaseModel):
    species1: str
    params1: dict = Field(default_factory=dict)
    species2: str
    params2: dict = Field(default_factory=dict)
    blend: float = Field(default=0.5, ge=0.0, le=1.0)
