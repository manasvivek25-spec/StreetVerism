"""Tourist /state assessment service with instruction synthesis and coverage calculation."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from fastapi import HTTPException

from shapely.geometry import Point, shape

from backend.app.geo import cell_to_latlng, latlng_to_cell
from backend.app.geo.h3_utils import cell_to_polygon_lnglat
from backend.app.models import Alert, Shelter, StateResponse
from backend.app.models.state import EvidenceItem, RenderedInstruction
from backend.app.repositories import ShelterRepo
from backend.app.scenario import Scenario
from backend.app.services.context import DataContext
from backend.app.services.shelters import get_nearest_shelters
from backend.app.services.templates import (
    SUPPORTED_LANGUAGES,
    render_instruction,
)
from backend.app.trust import assess_cell


def is_cell_in_service_bbox(cell: str, bbox_str: str) -> bool:
    """Check if cell centroid falls inside the configured service bounding box (min_lng,min_lat,max_lng,max_lat)."""
    try:
        parts = [float(p.strip()) for p in bbox_str.split(",")]
        if len(parts) != 4:
            return True
        min_lng, min_lat, max_lng, max_lat = parts
    except Exception:
        return True

    c_lat, c_lng = cell_to_latlng(cell)
    return min_lng <= c_lng <= max_lng and min_lat <= c_lat <= max_lat


def is_cell_in_scenario_groups(cell: str, scenario: Scenario) -> bool:
    """Check if cell centroid falls inside any scenario group polygon."""
    c_lat, c_lng = cell_to_latlng(cell)
    pt = Point(c_lng, c_lat)
    for group in scenario.area_groups:
        poly = group.polygon.model_dump() if hasattr(group.polygon, "model_dump") else group.polygon
        geom = shape(poly)
        if geom.contains(pt) or geom.touches(pt):
            return True
    return False


def get_state(
    lat: float,
    lng: float,
    lang: str,
    ctx: DataContext,
    shelter_repo: ShelterRepo,
    service_bbox: str = "80.10,12.80,80.40,13.30",
    scenario: Optional[Scenario] = None,
) -> StateResponse:
    """Assess crisis status, instructions, and nearest shelters for tourist coordinates."""
    # 1. Validate lat/lng ranges (422)
    if not (-90.0 <= lat <= 90.0):
        raise HTTPException(status_code=422, detail=f"Latitude {lat} out of range [-90.0, 90.0]")
    if not (-180.0 <= lng <= 180.0):
        raise HTTPException(status_code=422, detail=f"Longitude {lng} out of range [-180.0, 180.0]")

    # 2. Validate language (fallback to English)
    target_lang = lang if lang in SUPPORTED_LANGUAGES else "en"

    # 3. Resolve cell
    cell = latlng_to_cell(lat, lng, 8)

    # 4. Determine coverage status
    if ctx.mode == "replay" and scenario is not None:
        is_covered = is_cell_in_scenario_groups(cell, scenario)
    else:
        is_covered = is_cell_in_service_bbox(cell, service_bbox)

    coverage_status: Literal["covered", "outside"] = "covered" if is_covered else "outside"

    # 5. Assess with Bayesian trust engine
    features = ctx.features_provider(cell)
    cell_reports = ctx.reports_by_cell.get(cell, [])
    assessment = assess_cell(cell, features, cell_reports, ctx.alerts, ctx.now)

    # 6. Retrieve shelters & build shelter lookup map
    nearest = get_nearest_shelters(lat, lng, shelter_repo, limit=3)
    all_shelters = shelter_repo.list_all()
    shelter_map: Dict[str, str] = {s.id: s.name for s in all_shelters}

    # Identify fallback shelter name for SHELTER_AT
    fallback_shelter_name: Optional[str] = None
    if assessment.status in ("official_hazard", "likely_hazard"):
        open_nearest = [s for s in nearest if s.open]
        if open_nearest:
            fallback_shelter_name = open_nearest[0].name
        elif nearest:
            fallback_shelter_name = nearest[0].name

    # 7. Instruction key selection
    keys_to_render: List[str] = []
    alert_params: Dict[str, Any] = {}
    overlapping_official_alerts: List[Alert] = []

    if assessment.status == "official_hazard":
        # Find deciding hazard alerts overlapping this cell
        c_lat, c_lng = cell_to_latlng(cell)
        pt = Point(c_lng, c_lat)
        for a in ctx.alerts:
            if a.hazard != "all_clear":
                poly = shape(a.area.model_dump())
                if poly.contains(pt) or poly.touches(pt):
                    overlapping_official_alerts.append(a)

        if overlapping_official_alerts:
            deciding = overlapping_official_alerts[0]
            alert_params = deciding.params or {}
            # Deduplicate keys while preserving order
            seen_keys = set()
            for k in deciding.instruction_keys:
                if k not in seen_keys:
                    keys_to_render.append(k)
                    seen_keys.add(k)
        else:
            keys_to_render = ["MOVE_TO_HIGHER_GROUND", "AVOID_FLOODED_ROADS"]

    elif assessment.status == "likely_hazard":
        keys_to_render = ["AVOID_FLOODED_ROADS", "DO_NOT_CROSS_WATER", "FOLLOW_OFFICIAL_ONLY"]

    elif assessment.status == "unverified":
        keys_to_render = ["UNVERIFIED_WARNING", "FOLLOW_OFFICIAL_ONLY"]

    elif assessment.status == "contradicted":
        keys_to_render = ["FOLLOW_OFFICIAL_ONLY"]

    elif assessment.status == "clear":
        # Check if an official all_clear alert overlapping cell decided it
        c_lat, c_lng = cell_to_latlng(cell)
        pt = Point(c_lng, c_lat)
        all_clears = [
            a for a in ctx.alerts
            if a.hazard == "all_clear" and (shape(a.area.model_dump()).contains(pt) or shape(a.area.model_dump()).touches(pt))
        ]
        if all_clears:
            keys_to_render = ["ALL_CLEAR"]
            overlapping_official_alerts = all_clears
        else:
            keys_to_render = ["FOLLOW_OFFICIAL_ONLY"]

    # 8. Render instructions with parameter interpolation
    rendered_instructions: List[RenderedInstruction] = []
    for k in keys_to_render:
        inst = render_instruction(
            key=k,
            lang=target_lang,
            params=alert_params,
            fallback_shelter_name=fallback_shelter_name,
            shelter_map=shelter_map,
        )
        if inst is not None:
            rendered_instructions.append(inst)

    # 9. Format evidence breakdown
    evidence_items = [
        EvidenceItem(
            type=e.type,
            summary=e.summary,
            age_s=e.age_s,
            weight=e.weight,
        )
        for e in assessment.evidence
    ]

    server_time_iso = datetime.now(timezone.utc).isoformat()
    generated_at_iso = ctx.now.isoformat()

    return StateResponse(
        cell=cell,
        status=assessment.status,
        p_hazard=round(assessment.p_hazard, 4),
        headline_key=assessment.headline_key,
        alerts=overlapping_official_alerts,
        instructions=rendered_instructions,
        evidence=evidence_items,
        nearest_shelters=nearest,
        is_replay=ctx.is_replay,
        generated_at=generated_at_iso,
        server_time=server_time_iso,
        lang=target_lang,
        coverage=coverage_status,
        mode=ctx.mode,
        weather_available=bool(features.rain_available),
    )
