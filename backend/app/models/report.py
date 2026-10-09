"""Crowd report models for StreetVerism."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    """Payload for submitting a crowd ground-truth observation."""
    device_id: str = Field(..., description="Client device UUID")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    claim: Literal["flooded", "blocked", "safe"] = Field(
        ..., description="Ground observation claim"
    )
    text: Optional[str] = Field(default=None, max_length=500, description="Optional text description")


class ReportResponse(BaseModel):
    """Response when a crowd report is processed."""
    accepted: bool = True
    cell: str = Field(..., description="Affected H3 res-8 cell")
    status: str = Field(..., description="Updated cell status")
