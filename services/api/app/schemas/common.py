"""Pydantic models shared between SQLAlchemy JSON columns and the API schemas.

Keeping these in one module means the JSONB shape on disk is exactly the
shape the API serializes, and there's only one place to evolve it.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, RootModel

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class WeatherSnapshot(BaseModel):
    model_config = _FROZEN
    temp_c: float
    condition: str
    wind_kph: float
    source: str = "stub"


class ColorTag(BaseModel):
    model_config = _FROZEN
    name: str
    hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    weight: float = Field(ge=0.0, le=1.0)


class ConfidenceScores(RootModel[dict[str, float]]):
    """Per-attribute model confidence in [0, 1]. Keys are open-ended."""

    @property
    def min_confidence(self) -> float:
        return min(self.root.values()) if self.root else 0.0


class SizeMap(RootModel[dict[str, str | int]]):
    """Free-form size book: {"top": "M", "bottom": "32", "shoe_eu": 42}."""
