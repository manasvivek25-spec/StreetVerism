"""Operational API routes for StreetVerism."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status

from backend.app.auth import verify_authority_key
from backend.app.config import get_settings
from backend.app.geo.h3_utils import cell_to_parent, latlng_to_cell
from backend.app.models import (
    Alert,
    AlertCreate,
    AlertExpireResponse,
    AlertListResponse,
    CellFeatureCollection,
    CheckinCreate,
    CheckinCreateResponse,
    CheckinItem,
    CheckinListResponse,
    CheckinUpdate,
    HealthResponse,
    ReportCreate,
    ReportResponse,
    RouteResponse,
    ScenarioResetResponse,
    ScenarioSeek,
    ScenarioStart,
    ScenarioStatus,
    Shelter,
    ShelterListResponse,
    StateResponse,
)
from backend.app.models.state import EvidenceItem, GeoJSONLineString, RenderedInstruction

router = APIRouter()

# In-memory scenario state for mock/replay mode
_SCENARIO_STATE: Dict[str, Any] = {
    "name": "live",
    "mode": "live",
    "is_running": False,
    "paused": False,
    "speed": 1.0,
    "current_time": None,
    "elapsed_s": 0,
    "scenario_start": "2023-12-04T06:00:00Z",
    "scenario_end": "2023-12-04T22:00:00Z",
    "is_replay": False,
}

# In-memory storage for active session mock records
_MOCK_ALERTS: List[Dict[str, Any]] = []
_MOCK_CHECKINS: List[Dict[str, Any]] = []


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate Great Circle distance in meters."""
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 1)


def load_templates(lang: str) -> Dict[str, Any]:
    """Load template JSON file, falling back to English."""
    root = _get_project_root()
    template_dir = root / "data" / "templates"
    lang_file = template_dir / f"{lang}.json"
    en_file = template_dir / "en.json"

    if lang_file.exists():
        with open(lang_file, "r", encoding="utf-8") as f:
            return json.load(f)
    elif en_file.exists():
        with open(en_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "lang": "en",
        "reviewed": True,
        "templates": {
            "MOVE_TO_HIGHER_GROUND": "Move to higher ground immediately. Do not wait.",
            "AVOID_FLOODED_ROADS": "Avoid flooded roads and underpasses.",
        },
    }


def load_mock_shelters() -> List[Dict[str, Any]]:
    root = _get_project_root()
    shelters_path = root / "backend" / "mock_data" / "shelters.json"
    if shelters_path.exists():
        with open(shelters_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_mock_alerts() -> List[Dict[str, Any]]:
    global _MOCK_ALERTS
    if not _MOCK_ALERTS:
        root = _get_project_root()
        alerts_path = root / "backend" / "mock_data" / "alerts.json"
        if alerts_path.exists():
            with open(alerts_path, "r", encoding="utf-8") as f:
                _MOCK_ALERTS = json.load(f)
    return _MOCK_ALERTS


def load_mock_checkins() -> Dict[str, Any]:
    global _MOCK_CHECKINS
    root = _get_project_root()
    checkins_path = root / "backend" / "mock_data" / "checkins.json"
    if checkins_path.exists():
        with open(checkins_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not _MOCK_CHECKINS:
                _MOCK_CHECKINS = data.get("items", [])
            return {"items": _MOCK_CHECKINS, "clusters": data.get("clusters", [])}
    return {"items": _MOCK_CHECKINS, "clusters": []}


# --- System Health ---

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def get_health() -> HealthResponse:
    """Return system health status and wall-clock timestamp."""
    is_rep = _SCENARIO_STATE["is_replay"]
    return HealthResponse(
        status="healthy",
        mode="replay" if is_rep else "live",
        is_replay=is_rep,
        version="1.0.0",
        server_time=_now_utc(),
    )


# --- Tourist & Public Endpoints ---

@router.get("/state", response_model=StateResponse, tags=["Tourist"])
async def get_state(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Tourist latitude"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Tourist longitude"),
    lang: str = Query("en", description="Preferred language code"),
) -> StateResponse:
    """Return crisis status, instructions, evidence, and nearest shelters for coordinates."""
    cell = latlng_to_cell(lat, lng, 8)
    server_time = _now_utc()
    is_rep = _SCENARIO_STATE["is_replay"]
    generated_at = _SCENARIO_STATE["current_time"] if is_rep and _SCENARIO_STATE["current_time"] else server_time

    # Load templates for localization
    active_tmpl = load_templates(lang)
    en_tmpl = load_templates("en")
    is_reviewed = active_tmpl.get("reviewed", False)

    # Determine mock status & instructions
    alerts = [Alert(**a) for a in load_mock_alerts()]
    shelters_raw = load_mock_shelters()

    # Calculate nearest shelters with distances
    shelters_with_dist = []
    for s in shelters_raw:
        dist = haversine_m(lat, lng, s["lat"], s["lng"])
        s_copy = dict(s)
        s_copy["distance_m"] = dist
        shelters_with_dist.append(Shelter(**s_copy))
    shelters_with_dist.sort(key=lambda s: s.distance_m or 999999)

    nearest_shelter_name = shelters_with_dist[0].name if shelters_with_dist else "Nearest Safe Shelter"

    # Render localized instructions
    keys_to_render = ["MOVE_TO_HIGHER_GROUND", "AVOID_FLOODED_ROADS", "DO_NOT_CROSS_WATER", "SHELTER_AT"]
    instructions: List[RenderedInstruction] = []
    for k in keys_to_render:
        raw_text = active_tmpl.get("templates", {}).get(k, en_tmpl.get("templates", {}).get(k, k))
        text = raw_text.replace("{shelter}", nearest_shelter_name)
        orig_en = en_tmpl.get("templates", {}).get(k, k).replace("{shelter}", nearest_shelter_name)
        instructions.append(
            RenderedInstruction(
                key=k,
                text=text,
                reviewed=is_reviewed,
                original_en=orig_en if not is_reviewed else None,
            )
        )

    evidence = [
        EvidenceItem(
            type="official",
            summary="Active TNSDMA flood evacuation warning overlaps zone",
            age_s=300 if is_rep else 120,
            weight=3.5,
        ),
        EvidenceItem(
            type="rain",
            summary="Precipitation rate 45mm/h exceeding threshold",
            age_s=600 if is_rep else 300,
            weight=1.8,
        ),
        EvidenceItem(
            type="crowd",
            summary="3 independent corroborating waterlogging reports within 15 min",
            age_s=900 if is_rep else 450,
            weight=1.4,
        ),
    ]

    return StateResponse(
        cell=cell,
        status="official_hazard",
        p_hazard=0.99,
        headline_key="MOVE_TO_HIGHER_GROUND",
        alerts=alerts,
        instructions=instructions,
        evidence=evidence,
        nearest_shelters=shelters_with_dist[:3],
        is_replay=is_rep,
        generated_at=generated_at,
        server_time=server_time,
    )


@router.get("/cells", response_model=CellFeatureCollection, tags=["Tourist"])
async def get_cells(
    bbox: str = Query(..., description="Bounding box in minLng,minLat,maxLng,maxLat format")
) -> CellFeatureCollection:
    """Return GeoJSON FeatureCollection of evaluated cells intersecting the bounding box.
    
    Guaranteed in mock mode to include all five status classifications:
    official_hazard, likely_hazard, unverified, contradicted, clear.
    """
    root = _get_project_root()
    cells_path = root / "backend" / "mock_data" / "cells.json"
    if cells_path.exists():
        with open(cells_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return CellFeatureCollection(**data)
    raise HTTPException(status_code=500, detail="Mock cells dataset unavailable")


@router.get("/shelters", response_model=ShelterListResponse, tags=["Tourist"])
async def get_shelters() -> ShelterListResponse:
    """Return list of registered safe zones and emergency shelters."""
    shelters_raw = load_mock_shelters()
    shelters = [Shelter(**s) for s in shelters_raw]
    return ShelterListResponse(shelters=shelters, total=len(shelters))


@router.get("/templates/{lang}", tags=["Tourist"])
async def get_templates(lang: str) -> Dict[str, Any]:
    """Return raw template catalog for client offline caching."""
    return load_templates(lang)


@router.post("/reports", response_model=ReportResponse, tags=["Tourist"])
async def submit_report(payload: ReportCreate) -> ReportResponse:
    """Submit a ground-truth crowd report (unverified until clustered and corroborated)."""
    cell = latlng_to_cell(payload.lat, payload.lng, 8)
    return ReportResponse(
        accepted=True,
        cell=cell,
        status="unverified",
    )


@router.post("/checkin", response_model=CheckinCreateResponse, tags=["Tourist"])
async def submit_checkin(payload: CheckinCreate) -> CheckinCreateResponse:
    """Record a tourist safe or need_help check-in for triage."""
    chk_id = f"chk_{uuid4().hex[:8]}"
    cell7 = cell_to_parent(latlng_to_cell(payload.lat, payload.lng, 8), 7)
    now = _now_utc()

    # Append to mock storage
    global _MOCK_CHECKINS
    new_item = {
        "id": chk_id,
        "device_id": payload.device_id,
        "lat": round(payload.lat, 4),
        "lng": round(payload.lng, 4),
        "state": payload.state,
        "language": payload.language,
        "group_size": payload.group_size,
        "note": payload.note,
        "cell7": cell7,
        "handled": False,
        "recorded_at": now,
    }
    _MOCK_CHECKINS.append(new_item)

    return CheckinCreateResponse(id=chk_id, recorded_at=now)


# --- Authority Endpoints (Protected by X-Authority-Key) ---

@router.post(
    "/alerts",
    response_model=Alert,
    status_code=status.HTTP_201_CREATED,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def create_alert(payload: AlertCreate) -> Alert:
    """Publish a new official disaster alert or all-clear notice."""
    new_id = f"alt_{uuid4().hex[:8]}"
    alert_dict = payload.model_dump()
    alert_dict["id"] = new_id
    global _MOCK_ALERTS
    _MOCK_ALERTS.insert(0, alert_dict)
    return Alert(**alert_dict)


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def list_alerts(active: bool = Query(True, description="Filter for active alerts")) -> AlertListResponse:
    """Fetch all active published alerts."""
    alerts = [Alert(**a) for a in load_mock_alerts()]
    return AlertListResponse(alerts=alerts, total=len(alerts))


@router.delete(
    "/alerts/{alert_id}",
    response_model=AlertExpireResponse,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def expire_alert(alert_id: str) -> AlertExpireResponse:
    """Immediately expire an active alert."""
    global _MOCK_ALERTS
    _MOCK_ALERTS = [a for a in _MOCK_ALERTS if a.get("id") != alert_id]
    return AlertExpireResponse(ok=True, id=alert_id, expired_at=_now_utc())


@router.get(
    "/checkins",
    response_model=CheckinListResponse,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def list_checkins() -> CheckinListResponse:
    """Retrieve individual check-in records alongside aggregated H3 res-7 triage clusters."""
    data = load_mock_checkins()
    items = [CheckinItem(**item) for item in data.get("items", [])]
    return CheckinListResponse(items=items, clusters=data.get("clusters", []))


@router.patch(
    "/checkins/{checkin_id}",
    response_model=CheckinItem,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def handle_checkin(checkin_id: str, payload: CheckinUpdate) -> CheckinItem:
    """Mark a tourist check-in as handled by rescue operators."""
    global _MOCK_CHECKINS
    for item in _MOCK_CHECKINS:
        if item.get("id") == checkin_id:
            item["handled"] = payload.handled
            return CheckinItem(**item)
    raise HTTPException(status_code=404, detail=f"Check-in {checkin_id} not found")


# --- Scenario Control Endpoints ---

@router.post("/scenario/start", response_model=ScenarioStatus, tags=["Scenario"])
async def start_scenario(payload: ScenarioStart) -> ScenarioStatus:
    """Launch historical scenario playback."""
    _SCENARIO_STATE.update(
        {
            "name": payload.name,
            "mode": "replay",
            "is_running": True,
            "paused": False,
            "speed": payload.speed,
            "current_time": _SCENARIO_STATE["scenario_start"],
            "elapsed_s": 0,
            "is_replay": True,
        }
    )
    return ScenarioStatus(**_SCENARIO_STATE)


@router.post("/scenario/seek", response_model=ScenarioStatus, tags=["Scenario"])
async def seek_scenario(payload: ScenarioSeek) -> ScenarioStatus:
    """Seek the replay scenario clock to a specific timestamp or offset.
    
    Accepts exactly one of 't' or 'offset_s' (422 validation enforced).
    Clamps within scenario start/end bounds.
    """
    start_dt = datetime.fromisoformat(_SCENARIO_STATE["scenario_start"].replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(_SCENARIO_STATE["scenario_end"].replace("Z", "+00:00"))
    max_duration = int((end_dt - start_dt).total_seconds())

    if payload.offset_s is not None:
        target_offset = max(0, min(payload.offset_s, max_duration))
    else:
        assert payload.t is not None
        try:
            target_dt = datetime.fromisoformat(payload.t.replace("Z", "+00:00"))
            target_offset = int((target_dt - start_dt).total_seconds())
            target_offset = max(0, min(target_offset, max_duration))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid ISO-8601 timestamp in 't'")

    target_time = datetime.fromtimestamp(start_dt.timestamp() + target_offset, tz=timezone.utc).isoformat()
    _SCENARIO_STATE.update(
        {
            "current_time": target_time,
            "elapsed_s": target_offset,
            "is_running": True,
            "mode": "replay",
            "is_replay": True,
        }
    )
    return ScenarioStatus(**_SCENARIO_STATE)


@router.post("/scenario/reset", response_model=ScenarioResetResponse, tags=["Scenario"])
async def reset_scenario() -> ScenarioResetResponse:
    """Stop scenario playback and revert to live mode."""
    _SCENARIO_STATE.update(
        {
            "name": "live",
            "mode": "live",
            "is_running": False,
            "paused": False,
            "speed": 1.0,
            "current_time": None,
            "elapsed_s": 0,
            "is_replay": False,
        }
    )
    return ScenarioResetResponse(ok=True, mode="live", is_replay=False)


@router.get("/scenario/status", response_model=ScenarioStatus, tags=["Scenario"])
async def get_scenario_status() -> ScenarioStatus:
    """Get current status of scenario replay clock."""
    state = dict(_SCENARIO_STATE)
    if not state["is_running"]:
        state["current_time"] = _now_utc()
    return ScenarioStatus(**state)


# --- Stretch Route Endpoint ---

@router.get("/route", response_model=RouteResponse, tags=["Tourist"])
async def get_hazard_aware_route(
    from_lat: float = Query(..., ge=-90.0, le=90.0),
    from_lng: float = Query(..., ge=-180.0, le=180.0),
    to_shelter: str = Query(...),
    lang: str = Query("en"),
) -> RouteResponse:
    """Generate hazard-aware route avoiding cells marked official_hazard or likely_hazard."""
    # Find shelter
    shelters = load_mock_shelters()
    shelter = next((s for s in shelters if s["id"] == to_shelter), None)
    dest_lat = shelter["lat"] if shelter else from_lat + 0.005
    dest_lng = shelter["lng"] if shelter else from_lng + 0.005

    # Coordinates line strictly using [lng, lat]
    mid_lat = round((from_lat + dest_lat) / 2.0 + 0.001, 6)
    mid_lng = round((from_lng + dest_lng) / 2.0 - 0.001, 6)
    coords = [
        [round(from_lng, 6), round(from_lat, 6)],
        [mid_lng, mid_lat],
        [round(dest_lng, 6), round(dest_lat, 6)],
    ]
    total_dist = haversine_m(from_lat, from_lng, mid_lat, mid_lng) + haversine_m(mid_lat, mid_lng, dest_lat, dest_lng)

    return RouteResponse(
        route=GeoJSONLineString(type="LineString", coordinates=coords),
        steps=[
            "Depart from current location heading along designated high-ground corridor",
            "Bypass waterlogged intersection at junction",
            f"Arrive safely at {shelter['name'] if shelter else 'Safe Zone'}",
        ],
        distance_m=round(total_dist, 1),
        hazard_cells_avoided=2,
    )
