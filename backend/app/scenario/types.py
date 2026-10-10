"""Data types and models for StreetVerism Scenario and Replay Engine."""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from backend.app.models.alert import Alert, GeoJSONPolygon
from backend.app.trust.types import CellFeatures, Report

# Non-negotiable honesty constants
REPLAY_LABEL: str = "Replay: illustrative reconstruction"
REPLAY_DISCLAIMER: str = "Simulated data based loosely on a past event, not real or official."


class Bookmark(BaseModel):
    """Notable temporal marker in the scenario."""
    name: str
    t_offset_s: int
    description: str


class RainKeyframe(BaseModel):
    """Precipitation keyframe for temporal interpolation."""
    t_offset_s: int
    rain_mm_3h: float
    rain_mm_24h: float

    @field_validator("rain_mm_24h")
    @classmethod
    def _validate_24h_gte_3h(cls, v: float, info) -> float:
        r3 = info.data.get("rain_mm_3h")
        if r3 is not None and v < r3:
            raise ValueError(f"rain_mm_24h ({v}) must be greater than or equal to rain_mm_3h ({r3}).")
        return v


class RepresentativePoint(BaseModel):
    """Representative point well inside an area group."""
    name: str
    lat: float
    lng: float


class AreaGroup(BaseModel):
    """Geographic area group with rainfall keyframes."""
    id: str
    name: str
    representative_point: RepresentativePoint
    polygon: GeoJSONPolygon
    keyframes: List[RainKeyframe]


class ScenarioReport(BaseModel):
    """Serialized report in scenario JSON (stores lat/lng, cell computed on load)."""
    id: str
    device_id: str
    lat: float
    lng: float
    claim: str
    text: Optional[str] = None
    created_at: datetime
    tier: str = "default"


class Scenario(BaseModel):
    """Parsed and validated replay scenario."""
    name: str
    label: str
    disclaimer: str
    based_on: str
    is_replay: bool
    values_are_approximate: bool
    t0: datetime
    duration_s: int
    bookmarks: List[Bookmark] = Field(default_factory=list)
    area_groups: List[AreaGroup]
    alerts: List[Alert]
    reports: List[Report]


class ReplayInputs(BaseModel):
    """Point-in-time pure projection of scenario inputs for trust engine evaluation."""
    alerts: List[Alert]
    reports: List[Report]
    features_for_cell: Callable[[str, datetime], CellFeatures] = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True
