"""Alert models according to CONTEXT.md and docs/API.md contract."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class GeoJSONPolygon(BaseModel):
    """GeoJSON Polygon Geometry with [lng, lat] coordinate rings."""
    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]]


class AlertBase(BaseModel):
    """Core alert properties shared across creation and responses."""
    source: Literal["official_manual", "official_cap", "weather_api", "replay"] = Field(
        ..., description="Data origin for the alert"
    )
    sender: str = Field(..., description="Issuing agency, e.g. TNSDMA (demo)")
    hazard: Literal["flood", "cyclone", "heavy_rain", "all_clear"] = Field(
        ..., description="Hazard type or all_clear notice"
    )
    severity: Literal["minor", "moderate", "severe", "extreme"] = Field(
        ..., description="Severity category"
    )
    urgency: Literal["immediate", "expected", "future"] = Field(
        ..., description="Urgency of response needed"
    )
    certainty: Literal["observed", "likely", "possible"] = Field(
        ..., description="Degree of certainty"
    )
    area: GeoJSONPolygon = Field(
        ..., description="GeoJSON Polygon area where coordinates are [lng, lat]"
    )
    instruction_keys: List[str] = Field(
        default_factory=list, description="Template keys corresponding to safety instructions"
    )
    params: Dict[str, Any] = Field(
        default_factory=dict, description="Template parameters such as shelter IDs"
    )
    sent_at: str = Field(..., description="ISO-8601 UTC timestamp of publication")
    expires_at: str = Field(..., description="ISO-8601 UTC timestamp of alert expiry")
    supersedes: Optional[str] = Field(
        default=None, description="ID of a previous alert superseded by this one"
    )
    published_by: str = Field(..., description="Username or system identifier of publisher")
    is_replay: bool = Field(default=False, description="Flag indicating simulated replay data")

    @field_validator("params", mode="before")
    @classmethod
    def _ensure_params_dict(cls, v: Any) -> Dict[str, Any]:
        if v is None:
            return {}
        return v

    @field_validator("supersedes", mode="before")
    @classmethod
    def _ensure_supersedes_nullable(cls, v: Any) -> Optional[str]:
        if v is None or v == "":
            return None
        return v


class AlertCreate(AlertBase):
    """Alert publication payload without server-assigned ID."""
    pass


class Alert(AlertBase):
    """Full alert model containing server-assigned ID."""
    id: str = Field(..., description="Unique alert identifier")


class AlertListResponse(BaseModel):
    """Enveloped response for active alerts list."""
    alerts: List[Alert]
    total: int


class AlertExpireResponse(BaseModel):
    """Response when expiring an active alert."""
    ok: bool = True
    id: str
    expired_at: str
