"""Domain types, enums, and structured data classes for hazard-aware routing."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ManeuverEnum(str, Enum):
    """Standardized navigation maneuvers mapped from raw provider codes."""
    DEPART = "depart"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    SLIGHT_LEFT = "slight_left"
    SLIGHT_RIGHT = "slight_right"
    SHARP_LEFT = "sharp_left"
    SHARP_RIGHT = "sharp_right"
    CONTINUE = "continue"
    UTURN = "uturn"
    ROUNDABOUT = "roundabout"
    ARRIVE = "arrive"
    UNKNOWN = "unknown"


class RouteWarningEnum(str, Enum):
    """Fixed warning enum explaining routing constraints and fallbacks."""
    DESTINATION_IN_HAZARD = "destination_in_hazard"
    NO_HAZARD_FREE_ROUTE = "no_hazard_free_route"
    ROUTING_UNAVAILABLE = "routing_unavailable"
    UNVERIFIED_REPORTS_NEARBY = "unverified_reports_nearby"
    OUTSIDE_COVERAGE = "outside_coverage"
    START_IN_HAZARD = "start_in_hazard"


class RouteKindEnum(str, Enum):
    """Type of route geometry generated."""
    ROAD_ROUTE = "road_route"
    DIRECT_LINE = "direct_line"
    NONE = "none"
    MOCK = "mock"


class RoutingModeEnum(str, Enum):
    """Travel mode profile."""
    WALK = "walk"
    DRIVE = "drive"


class StructuredStep(BaseModel):
    """Vetted turn-by-turn navigation instruction without raw unvetted English text."""
    maneuver: ManeuverEnum = Field(..., description="Standardized movement action")
    street_name: Optional[str] = Field(default=None, description="Street or road name from map data, or null")
    distance_m: float = Field(..., ge=0.0, description="Maneuver step distance in meters")


class SafeDestination(BaseModel):
    """Emergency evacuation destination with spatial relative bearing and hazard status."""
    id: str = Field(..., description="Unique shelter identifier")
    name: str = Field(..., description="English shelter name")
    name_local: str = Field(..., description="Localized shelter name")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    distance_m: float = Field(..., ge=0.0, description="Haversine distance from origin in meters")
    bearing_deg: float = Field(..., ge=0.0, lt=360.0, description="Initial bearing from origin in degrees")
    compass_direction: str = Field(..., description="8-point compass sector: N, NE, E, SE, S, SW, W, NW")
    cell: str = Field(..., description="H3 resolution-8 cell of the shelter")
    status: str = Field(..., description="Bayesian hazard status of shelter cell")
    is_demo: bool = Field(default=True, description="Whether location is an illustrative demo center")


# Official attribution wording required by HeiGIT and OpenStreetMap
DEFAULT_ORS_ATTRIBUTION = "© openrouteservice by HeiGIT | Map data © OpenStreetMap contributors"


class AvoidSetResult(BaseModel):
    """Computed avoid set geometry and hazard cells for provider avoidance."""
    avoid_cells: List[str] = Field(default_factory=list, description="H3 resolution-8 hazard cells to avoid")
    avoid_polygon_geojson: Optional[Dict[str, Any]] = Field(
        default=None, description="GeoJSON Polygon or MultiPolygon with [lng, lat] coordinates"
    )
    shapely_union: Optional[Any] = Field(default=None, exclude=True, description="Shapely geometry object")
    warnings: List[RouteWarningEnum] = Field(default_factory=list)
    total_hazard_cells: int = Field(default=0, description="Count of hazard cells in vicinity")
    area_km2: float = Field(default=0.0, description="Area of avoid union in square kilometers")
    extent_km: float = Field(default=0.0, description="Max extent of avoid union bounding box in kilometers")
    pruned: bool = Field(default=False, description="Whether avoid set was pruned to keep within provider limits")
    is_exceeding_limits: bool = Field(default=False, description="Whether hazard set exceeded limits even after corridor pruning")


class RouteResult(BaseModel):
    """Internal result emitted by routing engine or provider adapter."""
    geometry: Dict[str, Any] = Field(..., description="GeoJSON LineString with [lng, lat] coordinate pairs")
    distance_m: float = Field(..., ge=0.0, description="Total route distance in meters")
    duration_s: Optional[float] = Field(default=None, ge=0.0, description="Estimated travel duration in seconds")
    steps: List[StructuredStep] = Field(default_factory=list, description="Structured step instructions")
    provider: Optional[str] = Field(default=None, description="Underlying road routing provider name")
    kind: RouteKindEnum = Field(..., description="Route classification")
    warnings: List[RouteWarningEnum] = Field(default_factory=list)
    hazard_cells_avoided: int = Field(default=0, description="Honest count of hazard cells avoided")
    attribution: Optional[str] = Field(default=None, description="Legal provider map attribution string")
