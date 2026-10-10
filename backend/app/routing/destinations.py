"""Emergency safe destination selection and spatial bearing calculations."""

import math
from typing import Any, Dict, List, Optional, Tuple

from backend.app.geo.h3_utils import haversine_distance_m, latlng_to_cell
from backend.app.routing.types import SafeDestination


def calculate_initial_bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate initial forward azimuth bearing in degrees [0.0, 360.0) from p1 to p2.
    
    Formula:
    θ = atan2(sin(Δλ)*cos(φ2), cos(φ1)*sin(φ2) − sin(φ1)*cos(φ2)*cos(Δλ))
    """
    if abs(lat1 - lat2) < 1e-9 and abs(lng1 - lng2) < 1e-9:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lng2 - lng1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)

    theta = math.atan2(y, x)
    bearing = (math.degrees(theta) + 360.0) % 360.0
    return round(bearing, 1)


def bearing_to_compass(bearing: float) -> str:
    """Convert an azimuth bearing in degrees [0.0, 360.0) to an 8-point compass sector."""
    sectors = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    # Each sector spans 45 degrees, centered around 0, 45, 90, etc.
    # N is 337.5 to 22.5
    index = int((bearing + 22.5) // 45.0) % 8
    return sectors[index]


def is_shelter_safe(
    shelter_lat: float,
    shelter_lng: float,
    assessments_by_cell: Dict[str, Any],
) -> Tuple[bool, str, str]:
    """Evaluate whether a shelter's enclosing H3 res-8 cell is safe.
    
    A shelter is considered unsafe if its cell is in official_hazard or likely_hazard.
    Returns (is_safe, cell_index, status_string).
    """
    cell = latlng_to_cell(shelter_lat, shelter_lng, res=8)
    assessment = assessments_by_cell.get(cell)

    if assessment is None:
        return True, cell, "clear"

    if hasattr(assessment, "status"):
        status_val = assessment.status
        status = status_val.value if hasattr(status_val, "value") else str(status_val)
    elif isinstance(assessment, dict):
        status = str(assessment.get("status", "clear"))
    else:
        status = "clear"

    is_safe = status not in ("official_hazard", "likely_hazard")
    return is_safe, cell, status


def select_safe_destinations(
    origin_lat: float,
    origin_lng: float,
    shelters: List[Dict[str, Any]],
    assessments_by_cell: Dict[str, Any],
    limit: int = 3,
) -> List[SafeDestination]:
    """Rank safe shelters by distance ascending and filter out hazard zones.
    
    Filters out any shelter whose cell is in official_hazard or likely_hazard.
    Calculates initial bearing (0-360°) and 8-point compass sector for each shelter.
    Returns up to `limit` safe destinations.
    """
    safe_candidates: List[SafeDestination] = []

    for sh in shelters:
        lat = float(sh["lat"])
        lng = float(sh["lng"])
        safe, cell, status = is_shelter_safe(lat, lng, assessments_by_cell)

        if not safe:
            continue

        dist_m = haversine_distance_m(origin_lat, origin_lng, lat, lng)
        bearing = calculate_initial_bearing(origin_lat, origin_lng, lat, lng)
        compass = bearing_to_compass(bearing)

        candidate = SafeDestination(
            id=str(sh.get("id", "")),
            name=str(sh.get("name", "Shelter")),
            name_local=str(sh.get("name_local") or sh.get("name", "")),
            lat=lat,
            lng=lng,
            distance_m=dist_m,
            bearing_deg=bearing,
            compass_direction=compass,
            cell=cell,
            status=status,
            is_demo=bool(sh.get("is_demo", True)),
        )
        safe_candidates.append(candidate)

    # Sort by distance ascending
    safe_candidates.sort(key=lambda s: s.distance_m)
    return safe_candidates[:limit]
