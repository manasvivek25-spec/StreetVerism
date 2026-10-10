"""Hazard-aware safe routing module for StreetVerism."""

from backend.app.routing.avoid import (
    DEFAULT_CORRIDOR_BUFFER_DEG,
    ORS_MAX_AVOID_AREA_KM2,
    ORS_MAX_AVOID_EXTENT_KM,
    ORS_MAX_AVOID_VERTICES,
    build_avoid_set,
    build_direct_line_route,
)
from backend.app.routing.destinations import (
    bearing_to_compass,
    calculate_initial_bearing,
    is_shelter_safe,
    select_safe_destinations,
)
from backend.app.routing.types import (
    DEFAULT_ORS_ATTRIBUTION,
    AvoidSetResult,
    ManeuverEnum,
    RouteKindEnum,
    RouteResult,
    RouteWarningEnum,
    RoutingModeEnum,
    SafeDestination,
    StructuredStep,
)

__all__ = [
    "DEFAULT_CORRIDOR_BUFFER_DEG",
    "DEFAULT_ORS_ATTRIBUTION",
    "ORS_MAX_AVOID_AREA_KM2",
    "ORS_MAX_AVOID_EXTENT_KM",
    "ORS_MAX_AVOID_VERTICES",
    "AvoidSetResult",
    "ManeuverEnum",
    "RouteKindEnum",
    "RouteResult",
    "RouteWarningEnum",
    "RoutingModeEnum",
    "SafeDestination",
    "StructuredStep",
    "bearing_to_compass",
    "build_avoid_set",
    "build_direct_line_route",
    "calculate_initial_bearing",
    "is_shelter_safe",
    "select_safe_destinations",
]
