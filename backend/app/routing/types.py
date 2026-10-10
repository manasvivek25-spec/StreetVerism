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
    SHELTER_UNREACHABLE = "shelter_unreachable"


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
    shelter_id: str = Field(..., description="Unique shelter identifier")
    id: Optional[str] = Field(default=None, description="Alias for shelter_id")
    name: str = Field(..., description="English shelter name")
    name_local: str = Field(..., description="Localized shelter name")
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    distance_m: float = Field(..., ge=0.0, description="Haversine distance from origin in meters")
    bearing_deg: float = Field(..., ge=0.0, lt=360.0, description="Initial bearing from origin in degrees")
    compass_direction: str = Field(..., description="8-point compass sector: N, NE, E, SE, S, SW, W, NW")
    cell: str = Field(..., description="H3 resolution-8 cell of the shelter")
    status: str = Field(..., description="Bayesian hazard status of shelter cell")
    is_safe: bool = Field(default=True, description="Whether shelter is in a safe cell")
    is_demo: bool = Field(default=True, description="Whether location is an illustrative demo center")

    def model_post_init(self, __context: Any) -> None:
        if self.id is None:
            self.id = self.shelter_id


class RouteWarningItem(BaseModel):
    """Structured warning with machine-readable key and human explanation."""
    key: str = Field(..., description="Fixed route warning enum key")
    detail: str = Field(..., description="Detailed explanation of the routing constraint")


class MapsUrls(BaseModel):
    """Native navigation links for universal fallback."""
    google: str
    apple: str
    geo: str


# Official attribution wording required by HeiGIT and OpenStreetMap
DEFAULT_ORS_ATTRIBUTION = "© openrouteservice by HeiGIT | Map data © OpenStreetMap contributors"

ROUTE_WARNING_DETAILS: Dict[str, str] = {
    RouteWarningEnum.DESTINATION_IN_HAZARD.value: "Selected shelter is located inside or adjacent to an active hazard zone.",
    RouteWarningEnum.NO_HAZARD_FREE_ROUTE.value: "No road path completely free of water could be found. Exercise extreme caution.",
    RouteWarningEnum.ROUTING_UNAVAILABLE.value: "Road navigation provider is currently offline or rate-limited. Straight-line bearing displayed.",
    RouteWarningEnum.UNVERIFIED_REPORTS_NEARBY.value: "Unverified crowd reports exist near your travel corridor. Exercise caution.",
    RouteWarningEnum.OUTSIDE_COVERAGE.value: "Your location is outside the active emergency monitoring boundary.",
    RouteWarningEnum.START_IN_HAZARD.value: "Your current position is inside an active flood hazard zone. Move immediately toward safety.",
    RouteWarningEnum.SHELTER_UNREACHABLE.value: "All known shelters are unreachable or flooded. Seek nearest high ground.",
}


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


class RouteResponse(BaseModel):
    """Complete public safe-route response complying with frozen contract specification."""
    route_id: str
    route_version: int = 1
    valid_until: str
    kind: RouteKindEnum
    destination: Optional[SafeDestination] = None
    alternatives: List[SafeDestination] = Field(default_factory=list)
    geometry: Optional[Dict[str, Any]] = None
    distance_m: float = 0.0
    duration_s: Optional[float] = None
    steps: List[StructuredStep] = Field(default_factory=list)
    warnings: List[RouteWarningItem] = Field(default_factory=list)
    hazard_cells_avoided: int = 0
    maps_urls: Optional[MapsUrls] = None
    attribution: Optional[str] = None
    provider: Optional[str] = None
    reroute: bool = False
    reason_hint: Optional[str] = None
    is_replay: bool = False
    mode_of_data: Literal["live", "replay", "mock"] = "live"
    generated_at: str
