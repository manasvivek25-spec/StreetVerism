"""Emergency shelter models."""

from typing import List, Optional
from pydantic import BaseModel, Field


class Shelter(BaseModel):
    """Emergency evacuation center or safe shelter."""
    id: str = Field(..., description="Unique shelter identifier")
    name: str = Field(..., description="English/Latin name of shelter")
    name_local: str = Field(..., description="Local script name, e.g. Tamil")
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    open: bool = Field(default=True, description="Whether shelter is currently accepting evacuees")
    is_demo: bool = Field(default=True, description="Indicates demonstration/sample shelter data")
    capacity: Optional[int] = Field(default=None, description="Max shelter occupancy")
    distance_m: Optional[float] = Field(default=None, description="Computed distance from tourist location in meters")


class ShelterListResponse(BaseModel):
    """Enveloped response for shelter catalog."""
    shelters: List[Shelter]
    total: int
