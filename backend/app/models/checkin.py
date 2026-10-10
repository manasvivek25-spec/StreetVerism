"""Tourist check-in models for crisis triage."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class CheckinCreate(BaseModel):
    """Tourist check-in submission."""
    device_id: str = Field(..., description="Device UUID")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    state: Literal["safe", "need_help"] = Field(..., description="Tourist safety condition")
    language: str = Field(default="en", description="Tourist preferred language code")
    group_size: int = Field(default=1, ge=1, le=50, description="Number of people in traveling group")
    note: Optional[str] = Field(default=None, max_length=500, description="Optional SOS or medical note")


class CheckinCreateResponse(BaseModel):
    """Response after check-in is logged."""
    id: str
    recorded_at: str


class CheckinItem(BaseModel):
    """Full check-in record for authority view (device_id stripped in live/replay for privacy)."""
    id: str
    device_id: Optional[str] = Field(default=None, description="Device UUID (omitted in live/replay mode)")
    lat: float
    lng: float
    state: Literal["safe", "need_help"]
    language: str
    group_size: int
    note: Optional[str] = None
    cell7: str = Field(..., description="Aggregated parent H3 res-7 cell")
    handled: bool = False
    created_at: Optional[str] = Field(default=None, description="UTC ISO-8601 creation timestamp")
    recorded_at: Optional[str] = Field(default=None, description="UTC ISO-8601 recording timestamp")
    is_replay: bool = Field(default=False, description="True if submitted during scenario replay")


class CheckinUpdate(BaseModel):
    """Payload to update handling status of a check-in."""
    handled: bool


class CheckinCluster(BaseModel):
    """Aggregated triage cluster grouped by H3 res-7 cell."""
    cell7: str
    count: int
    need_help: int
    languages: Dict[str, int]
    unhandled_need_help: int = Field(default=0, description="Count of unhandled need_help check-ins")


class CheckinListResponse(BaseModel):
    """Enveloped response for check-ins and clustered triage."""
    items: List[CheckinItem]
    clusters: List[CheckinCluster]
