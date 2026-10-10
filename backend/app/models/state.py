"""Tourist crisis state and system health response models."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from .alert import Alert
from .cell import CellStatus
from .shelter import Shelter


class RenderedInstruction(BaseModel):
    """Safety action rendered from reviewed or translated template."""
    key: str = Field(..., description="Template key identifier")
    text: str = Field(..., description="Localized text message")
    reviewed: bool = Field(..., description="True if vetted by humans (en, hi, ta)")
    original_en: Optional[str] = Field(default=None, description="English fallback text when machine-translated")


class EvidenceItem(BaseModel):
    """Explainable Bayesian evidence component contributing to cell status."""
    type: Literal["official", "rain", "crowd"] = Field(..., description="Source of evidence")
    summary: str = Field(..., description="Human-readable explanation for Why UI")
    age_s: int = Field(..., description="Age of evidence relative to effective clock in seconds")
    weight: float = Field(..., description="Calculated log-odds or probability contribution")


class StateResponse(BaseModel):
    """Unified crisis response returned to tourist PWA for their location."""
    cell: str = Field(..., description="Current H3 res-8 cell")
    status: CellStatus = Field(..., description="Cell hazard classification")
    p_hazard: float = Field(..., ge=0.0, le=1.0, description="Posterior hazard probability")
    headline_key: str = Field(..., description="Dominant template key for UI banner")
    alerts: List[Alert] = Field(default_factory=list, description="Active official alerts covering this cell")
    instructions: List[RenderedInstruction] = Field(
        default_factory=list, description="Rendered prioritized safety actions"
    )
    evidence: List[EvidenceItem] = Field(
        default_factory=list, description="Transparent Bayesian evidence list"
    )
    nearest_shelters: List[Shelter] = Field(
        default_factory=list, description="Nearby open evacuation centers"
    )
    is_replay: bool = Field(default=False, description="Whether state is emitted by replay engine")
    generated_at: str = Field(..., description="Timestamp based on effective clock (scenario clock in replay)")
    server_time: str = Field(..., description="Actual server wall-clock time (ISO-8601 UTC)")
    lang: str = Field(default="en", description="Language code actually served")
    coverage: Literal["covered", "outside"] = Field(default="covered", description="Service bbox or scenario group coverage status")
    mode: Literal["live", "replay", "mock"] = Field(default="live", description="Operating mode of the system")


class HealthResponse(BaseModel):
    """System liveness and configuration status."""
    status: str = "healthy"
    mode: Literal["live", "replay", "mock"] = "live"
    is_replay: bool = False
    version: str = "1.0.0"
    server_time: str
    replay: Optional[Dict[str, Any]] = Field(default=None, description="Public replay banner details when mode is replay")


class GeoJSONLineString(BaseModel):
    """GeoJSON LineString with [lng, lat] vertices."""
    type: Literal["LineString"] = "LineString"
    coordinates: List[List[float]]


class RouteResponse(BaseModel):
    """Hazard-aware evacuation route avoiding hazard cells."""
    route: GeoJSONLineString
    steps: List[str]
    distance_m: float
    hazard_cells_avoided: int
