from typing import Literal

from pydantic import BaseModel, Field


class GenerationParams(BaseModel):
    mode: Literal["heightmap", "lithophane", "emboss", "relief", "ai-depth"] = "heightmap"
    preset: Literal["custom", "ender3_v3", "prusa_mk4", "bambu_a1_mini"] = "custom"
    max_height: float = Field(default=8.0, ge=0.5, le=40.0)
    base_thickness: float = Field(default=2.0, ge=0.5, le=20.0)
    gamma: float = Field(default=1.0, ge=0.2, le=3.0)
    smooth_sigma: float = Field(default=0.0, ge=0.0, le=5.0)
    resolution: int = Field(default=192, ge=32, le=512)
    target_width_mm: float = Field(default=100.0, ge=20.0, le=300.0)
    adaptive_remesh: bool = False
