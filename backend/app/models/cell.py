"""H3 Cell and GeoJSON Feature models."""

from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field

CellStatus = Literal["official_hazard", "likely_hazard", "unverified", "contradicted", "clear"]


class CellProperties(BaseModel):
    """Properties for an evaluated H3 cell."""
    cell: str = Field(..., description="H3 index string at resolution 8")
    status: CellStatus = Field(..., description="Deterministic status classification")
    p_hazard: float = Field(..., ge=0.0, le=1.0, description="Posterior probability of hazard")
    updated_at: str = Field(..., description="ISO-8601 UTC timestamp")


class GeoJSONPolygonGeometry(BaseModel):
    """GeoJSON Polygon Geometry strictly containing [lng, lat] coordinate rings."""
    type: Literal["Polygon"] = "Polygon"
    coordinates: List[List[List[float]]]


class CellFeature(BaseModel):
    """GeoJSON Feature representing a single H3 cell boundary and status."""
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONPolygonGeometry
    properties: CellProperties


class CellFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection returned by /api/cells."""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[CellFeature]
