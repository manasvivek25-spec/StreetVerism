"""Manual alert publication normalization and validation for StreetVerism."""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shapely.geometry import Polygon
from shapely.validation import explain_validity

from backend.app.config import get_settings
from backend.app.db import to_utc_iso
from backend.app.models import Alert, AlertCreate, GeoJSONPolygon
from backend.app.repositories import ShelterRepo

# Constraints
MAX_POLYGON_VERTICES = 500
MAX_POLYGON_AREA_KM2 = 25000.0  # Approx half area of Tamil Nadu

# Severity-based default expiry durations if not supplied
SEVERITY_DEFAULT_DURATIONS = {
    "extreme": timedelta(hours=6),
    "severe": timedelta(hours=12),
    "moderate": timedelta(hours=24),
    "minor": timedelta(hours=48),
}


def _get_vetted_template_keys() -> List[str]:
    """Load canonical vetted template keys from data/templates/en.json."""
    tmpl_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "templates" / "en.json"
    if tmpl_path.exists():
        with open(tmpl_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return list(data.get("templates", {}).keys())
    return [
        "MOVE_TO_HIGHER_GROUND",
        "AVOID_FLOODED_ROADS",
        "DO_NOT_CROSS_WATER",
        "SHELTER_AT",
        "STAY_INDOORS",
        "STAY_AWAY_FROM_COAST",
        "KEEP_PHONE_CHARGED",
        "ALL_CLEAR",
        "EMERGENCY_NUMBER",
        "FOLLOW_OFFICIAL_ONLY",
        "CHECKIN_PROMPT",
        "UNVERIFIED_WARNING",
    ]


def calculate_polygon_area_km2(coordinates: List[List[float]]) -> float:
    """Calculate approximate spherical polygon area in square kilometers."""
    if len(coordinates) < 4:
        return 0.0
    # Mean latitude for longitude scaling
    mean_lat = sum(pt[1] for pt in coordinates) / len(coordinates)
    lat_km_per_deg = 111.132
    lng_km_per_deg = 111.320 * math.cos(math.radians(mean_lat))

    # Project coordinates to km plane
    km_coords = [(pt[0] * lng_km_per_deg, pt[1] * lat_km_per_deg) for pt in coordinates]
    poly = Polygon(km_coords)
    return abs(poly.area)


def validate_and_repair_polygon(coordinates: List[List[List[float]]]) -> GeoJSONPolygon:
    """Validate GeoJSON polygon geometry, vertices count, coordinate ranges, and repair self-intersections."""
    if not coordinates or not coordinates[0]:
        raise ValueError("Polygon coordinates cannot be empty.")

    exterior_ring = coordinates[0]

    # Vertex count cap
    if len(exterior_ring) > MAX_POLYGON_VERTICES:
        raise ValueError(
            f"Polygon exceeds maximum allowed vertices ({len(exterior_ring)} > {MAX_POLYGON_VERTICES})."
        )

    # Coordinate range validation: [lng, lat]
    for pt in exterior_ring:
        if len(pt) < 2:
            raise ValueError("Coordinates must be [lng, lat] pairs.")
        lng, lat = pt[0], pt[1]
        if not (-180.0 <= lng <= 180.0):
            raise ValueError(f"Longitude out of bounds [-180, 180]: {lng}")
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude out of bounds [-90, 90]: {lat}")

    # Area cap check
    area_km2 = calculate_polygon_area_km2(exterior_ring)
    if area_km2 > MAX_POLYGON_AREA_KM2:
        raise ValueError(
            f"Polygon area ({area_km2:.1f} km²) exceeds maximum allowable area of {MAX_POLYGON_AREA_KM2} km²."
        )

    shapely_poly = Polygon(exterior_ring)
    if shapely_poly.is_empty:
        raise ValueError("Polygon geometry is empty.")

    if not shapely_poly.is_valid:
        # Attempt auto-repair via buffer(0)
        repaired = shapely_poly.buffer(0)
        if not repaired.is_valid or repaired.is_empty or not isinstance(repaired, Polygon):
            reason = explain_validity(shapely_poly)
            raise ValueError(f"Irreparable self-intersecting polygon geometry: {reason}")
        shapely_poly = repaired

    # Extract repaired closed coordinates
    coords = [[round(coord[0], 6), round(coord[1], 6)] for coord in list(shapely_poly.exterior.coords)]
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])

    return GeoJSONPolygon(coordinates=[coords])


def normalize_manual_alert(
    payload: AlertCreate,
    shelter_repo: Optional[ShelterRepo] = None,
    now: Optional[datetime] = None,
) -> Alert:
    """Normalize and validate a manual alert publication request."""
    current_time = now or datetime.now(timezone.utc)
    settings = get_settings()

    # 1. Enums validation handled by Pydantic model (hazard, severity, urgency, certainty)
    # 2. Polygon validity & repair
    valid_polygon = validate_and_repair_polygon(payload.area.coordinates)

    # 3. Timestamps & Expiry
    sent_iso = to_utc_iso(payload.sent_at or current_time)
    sent_dt = datetime.fromisoformat(sent_iso.replace("Z", "+00:00"))

    if payload.expires_at:
        exp_iso = to_utc_iso(payload.expires_at)
        exp_dt = datetime.fromisoformat(exp_iso.replace("Z", "+00:00"))
    else:
        duration = SEVERITY_DEFAULT_DURATIONS.get(payload.severity, timedelta(hours=12))
        exp_dt = sent_dt + duration
        exp_iso = to_utc_iso(exp_dt)

    if sent_dt >= exp_dt:
        raise ValueError(f"Alert sent_at ({sent_iso}) must be strictly earlier than expires_at ({exp_iso}).")

    # 4. Instruction keys rules
    vetted_keys = _get_vetted_template_keys()
    for k in payload.instruction_keys:
        if k not in vetted_keys:
            raise ValueError(f"Unknown instruction key '{k}'. Must be one of vetted keys: {vetted_keys}")

    if payload.hazard == "all_clear":
        if "ALL_CLEAR" not in payload.instruction_keys:
            raise ValueError("Alerts with hazard='all_clear' must include 'ALL_CLEAR' in instruction_keys.")
    else:
        if not payload.instruction_keys:
            raise ValueError(f"Hazard alert ('{payload.hazard}') must include at least one instruction key.")

    # 5. Shelter parameter check (MOCK=0 only)
    shelter_id = payload.params.get("shelter")
    if shelter_id and not settings.mock and shelter_repo is not None:
        shelter = shelter_repo.get(shelter_id)
        if not shelter:
            raise ValueError(f"Specified shelter ID '{shelter_id}' does not exist in shelters registry.")

    alert_id = f"alt_{uuid4().hex[:8]}"

    return Alert(
        id=alert_id,
        source="official_manual",
        sender=payload.sender,
        hazard=payload.hazard,
        severity=payload.severity,
        urgency=payload.urgency,
        certainty=payload.certainty,
        area=valid_polygon,
        instruction_keys=payload.instruction_keys,
        params=payload.params,
        sent_at=sent_iso,
        expires_at=exp_iso,
        supersedes=payload.supersedes,
        published_by=payload.published_by,
        is_replay=payload.is_replay,
    )
