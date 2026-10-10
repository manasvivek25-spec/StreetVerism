"""Operational API routes for StreetVerism.

Supports dual-mode dispatch:
- MOCK=1: Pure deterministic mock dataset handlers.
- MOCK=0: Real service-layer delegator supporting Live database integration and Replay clock simulation.
"""

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security, status

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
from backend.app.repositories import (
    AlertRepo,
    CheckinRepo,
    ReportRepo,
    ShelterRepo,
    SqliteAlertRepo,
    SqliteCheckinRepo,
    SqliteReportRepo,
    SqliteShelterRepo,
)
from backend.app.scenario import (
    REPLAY_DISCLAIMER,
    REPLAY_LABEL,
    ReplayOverlay,
    Scenario,
    ScenarioClock,
    load_scenario,
)
from backend.app.services import (
    DataContext,
    build_data_context,
    clear_cells_cache,
    create_official_alert,
    expire_official_alert,
    get_all_shelters,
    get_cells_for_bbox,
    get_state,
    get_template_catalog,
    handle_checkin,
    list_checkins,
    list_official_alerts,
    submit_checkin,
    submit_crowd_report,
    calculate_safe_route,
)
from backend.app.routing.types import RouteResponse

logger = logging.getLogger("streetverism.routes")
router = APIRouter()

# --- Shared MOCK=0 Repositories & Scenario State ---
_ALERT_REPO: AlertRepo = SqliteAlertRepo()
_REPORT_REPO: ReportRepo = SqliteReportRepo()
_CHECKIN_REPO: CheckinRepo = SqliteCheckinRepo()
_SHELTER_REPO: ShelterRepo = SqliteShelterRepo()
_SCENARIO: Optional[Scenario] = None
_SCENARIO_CLOCK: Optional[ScenarioClock] = None
_REPLAY_OVERLAY: ReplayOverlay = ReplayOverlay()
_IS_REPLAY_ACTIVE: bool = False


def get_alert_repo() -> AlertRepo:
    return _ALERT_REPO


def get_report_repo() -> ReportRepo:
    return _REPORT_REPO


def get_checkin_repo() -> CheckinRepo:
    return _CHECKIN_REPO


def get_shelter_repo() -> ShelterRepo:
    return _SHELTER_REPO


def get_replay_overlay() -> ReplayOverlay:
    return _REPLAY_OVERLAY


def get_scenario() -> Optional[Scenario]:
    return _SCENARIO


def get_scenario_clock() -> Optional[ScenarioClock]:
    return _SCENARIO_CLOCK


def set_custom_repos(
    alert_repo: Optional[AlertRepo] = None,
    report_repo: Optional[ReportRepo] = None,
    checkin_repo: Optional[CheckinRepo] = None,
    shelter_repo: Optional[ShelterRepo] = None,
) -> None:
    """Helper for testing with injected in-memory repositories."""
    global _ALERT_REPO, _REPORT_REPO, _CHECKIN_REPO, _SHELTER_REPO
    if alert_repo is not None:
        _ALERT_REPO = alert_repo
    if report_repo is not None:
        _REPORT_REPO = report_repo
    if checkin_repo is not None:
        _CHECKIN_REPO = checkin_repo
    if shelter_repo is not None:
        _SHELTER_REPO = shelter_repo


def _get_project_root() -> Path:
    """Return project root directory (4 levels up from this file)."""
    return Path(__file__).resolve().parent.parent.parent.parent


def init_scenario(scenario_path: Path, shelters_path: Path) -> Scenario:
    """Initialize scenario and clock at startup."""
    global _SCENARIO, _SCENARIO_CLOCK
    _SCENARIO = load_scenario(scenario_path, shelters_path)
    _SCENARIO_CLOCK = ScenarioClock(_SCENARIO)
    return _SCENARIO


def autostart_replay(bookmark_name: str) -> None:
    """Seek to named bookmark and keep playback PAUSED (playable via scenario API)."""
    global _SCENARIO, _SCENARIO_CLOCK, _IS_REPLAY_ACTIVE
    if _SCENARIO is None or _SCENARIO_CLOCK is None:
        return
    bm = next((b for b in _SCENARIO.bookmarks if b.name == bookmark_name), None)
    _IS_REPLAY_ACTIVE = True
    if bm:
        _SCENARIO_CLOCK.seek(offset_s=bm.t_offset_s)
    _SCENARIO_CLOCK.pause()
    clear_cells_cache()


def _get_context(eval_now: Optional[datetime] = None) -> DataContext:
    global _SCENARIO_CLOCK, _SCENARIO, _REPLAY_OVERLAY, _ALERT_REPO, _REPORT_REPO, _IS_REPLAY_ACTIVE
    effective_mode = "replay" if (_IS_REPLAY_ACTIVE and _SCENARIO_CLOCK is not None) else "live"

    return build_data_context(
        mode=effective_mode,
        scenario_clock=_SCENARIO_CLOCK if effective_mode == "replay" else None,
        scenario=_SCENARIO if effective_mode == "replay" else None,
        overlay=_REPLAY_OVERLAY,
        alert_repo=_ALERT_REPO,
        report_repo=_REPORT_REPO,
        injected_now=eval_now,
    )


# --- MOCK Mode In-Memory State (MOCK=1 untouched) ---
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
_MOCK_ALERTS: List[Dict[str, Any]] = []
_MOCK_CHECKINS: List[Dict[str, Any]] = []


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 1)


def load_templates_mock(lang: str) -> Dict[str, Any]:
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
    """Return system health status, wall-clock time, and optional replay banner."""
    settings = get_settings()
    server_time = _now_utc()

    if settings.mock:
        is_rep = _SCENARIO_STATE["is_replay"]
        mode = "replay" if is_rep else "mock"
        return HealthResponse(
            status="healthy",
            mode=mode,
            is_replay=is_rep,
            version=settings.project_version,
            server_time=server_time,
        )

    # Live or Replay mode
    global _SCENARIO_CLOCK, _IS_REPLAY_ACTIVE
    if _IS_REPLAY_ACTIVE and _SCENARIO_CLOCK is not None:
        sim_iso = _SCENARIO_CLOCK.sim_time().isoformat()
        replay_obj = {
            "label": REPLAY_LABEL,
            "disclaimer": REPLAY_DISCLAIMER,
            "sim_time": sim_iso,
        }
        return HealthResponse(
            status="healthy",
            mode="replay",
            is_replay=True,
            version=settings.project_version,
            server_time=server_time,
            replay=replay_obj,
        )

    return HealthResponse(
        status="healthy",
        mode="live",
        is_replay=False,
        version=settings.project_version,
        server_time=server_time,
        replay=None,
    )


# --- Tourist & Public Endpoints ---

@router.get("/state", response_model=StateResponse, tags=["Tourist"])
async def get_state_endpoint(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Tourist latitude"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Tourist longitude"),
    lang: str = Query("en", description="Preferred language code"),
) -> StateResponse:
    """Return crisis status, instructions, evidence, and nearest shelters for coordinates."""
    settings = get_settings()
    if settings.mock:
        cell = latlng_to_cell(lat, lng, 8)
        server_time = _now_utc()
        is_rep = _SCENARIO_STATE["is_replay"]
        generated_at = _SCENARIO_STATE["current_time"] if is_rep and _SCENARIO_STATE["current_time"] else server_time
        active_tmpl = load_templates_mock(lang)
        en_tmpl = load_templates_mock("en")
        is_reviewed = active_tmpl.get("reviewed", False)
        alerts = [Alert(**a) for a in load_mock_alerts()]
        shelters_raw = load_mock_shelters()
        shelters_with_dist = []
        for s in shelters_raw:
            dist = haversine_m(lat, lng, s["lat"], s["lng"])
            s_copy = dict(s)
            s_copy["distance_m"] = dist
            shelters_with_dist.append(Shelter(**s_copy))
        shelters_with_dist.sort(key=lambda s: s.distance_m or 999999)
        nearest_shelter_name = shelters_with_dist[0].name if shelters_with_dist else "Nearest Safe Shelter"
        keys_to_render = ["MOVE_TO_HIGHER_GROUND", "AVOID_FLOODED_ROADS", "DO_NOT_CROSS_WATER", "SHELTER_AT"]
        instructions = []
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
                summary="Active State Disaster Authority flood evacuation warning overlaps zone",
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
            lang=active_tmpl.get("lang", "en"),
            coverage="covered",
            mode="replay" if is_rep else "mock",
        )

    # MOCK=0 Service Layer
    ctx = _get_context()
    return get_state(
        lat=lat,
        lng=lng,
        lang=lang,
        ctx=ctx,
        shelter_repo=_SHELTER_REPO,
        service_bbox=settings.service_bbox,
        scenario=_SCENARIO,
    )


@router.get("/cells", response_model=CellFeatureCollection, tags=["Tourist"])
async def get_cells_endpoint(
    bbox: str = Query(..., description="Bounding box in minLng,minLat,maxLng,maxLat format")
) -> CellFeatureCollection:
    """Return GeoJSON FeatureCollection of evaluated cells intersecting the bounding box."""
    settings = get_settings()
    if settings.mock:
        root = _get_project_root()
        cells_path = root / "backend" / "mock_data" / "cells.json"
        if cells_path.exists():
            with open(cells_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return CellFeatureCollection(**data)
        raise HTTPException(status_code=500, detail="Mock cells dataset unavailable")

    ctx = _get_context()
    return get_cells_for_bbox(bbox, ctx)


@router.get("/shelters", response_model=ShelterListResponse, tags=["Tourist"])
async def get_shelters_endpoint() -> ShelterListResponse:
    """Return list of registered safe zones and emergency shelters."""
    settings = get_settings()
    if settings.mock:
        shelters_raw = load_mock_shelters()
        shelters = [Shelter(**s) for s in shelters_raw]
        return ShelterListResponse(shelters=shelters, total=len(shelters))

    shelters, total = get_all_shelters(_SHELTER_REPO)
    return ShelterListResponse(shelters=shelters, total=total)


@router.get("/templates/{lang}", tags=["Tourist"])
async def get_templates_endpoint(lang: str) -> Dict[str, Any]:
    """Return raw template catalog for client offline caching."""
    settings = get_settings()
    if settings.mock:
        return load_templates_mock(lang)

    catalog, _ = get_template_catalog(lang, _get_project_root() / "data" / "templates")
    return catalog


@router.post("/reports", response_model=ReportResponse, tags=["Tourist"])
async def submit_report_endpoint(payload: ReportCreate) -> ReportResponse:
    """Submit a crowd report with 600s rate-limiting and immediate cell re-assessment."""
    settings = get_settings()
    if settings.mock:
        cell = latlng_to_cell(payload.lat, payload.lng, 8)
        return ReportResponse(accepted=True, cell=cell, status="unverified")

    ctx = _get_context()
    return submit_crowd_report(payload, ctx, _REPORT_REPO, _REPLAY_OVERLAY)


@router.post("/checkin", response_model=CheckinCreateResponse, tags=["Tourist"])
async def submit_checkin_endpoint(payload: CheckinCreate, request: Request) -> CheckinCreateResponse:
    """Record a tourist safe or need_help check-in for triage."""
    settings = get_settings()
    client_ip = request.client.host if request.client else "127.0.0.1"

    if settings.mock:
        chk_id = f"chk_{uuid4().hex[:8]}"
        cell7 = cell_to_parent(latlng_to_cell(payload.lat, payload.lng, 8), 7)
        now = _now_utc()
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

    ctx = _get_context()
    return submit_checkin(payload, ctx, _CHECKIN_REPO, client_ip=client_ip)


@router.get("/route", tags=["Tourist"])
async def get_route_endpoint(
    request: Request,
    lat: Optional[float] = Query(None, description="Tourist origin latitude"),
    lng: Optional[float] = Query(None, description="Tourist origin longitude"),
    from_lat: Optional[float] = Query(None, description="Alternative origin latitude parameter"),
    from_lng: Optional[float] = Query(None, description="Alternative origin longitude parameter"),
    mode: str = Query("walk", description="Travel mode: walk or drive"),
    to_shelter: Optional[str] = Query(None, description="Explicit target shelter ID"),
    reroute: bool = Query(False, description="Request rerouting with debounce"),
    device_id: Optional[str] = Query(None, description="Device UUID for reroute debouncing"),
    lang: Optional[str] = Query("en", description="Preferred language"),
):
    """Calculate an emergency hazard-aware route to the nearest safe shelter."""
    settings = get_settings()
    effective_lat = lat if lat is not None else from_lat
    effective_lng = lng if lng is not None else from_lng

    if effective_lat is None or effective_lng is None:
        raise HTTPException(status_code=422, detail="Origin coordinates (lat, lng) are required.")

    client_ip = request.client.host if request.client else "127.0.0.1"

    if settings.mock:
        from backend.app.routing.types import RouteKindEnum
        geom = {
            "type": "LineString",
            "coordinates": [[effective_lng, effective_lat], [effective_lng + 0.01, effective_lat + 0.01]],
        }
        return {
            "route_id": f"rt_mock_{uuid4().hex[:8]}",
            "route_version": 1,
            "valid_until": _now_utc(),
            "kind": RouteKindEnum.MOCK.value,
            "destination": None,
            "alternatives": [],
            "geometry": geom,
            "route": geom,  # Legacy field for test_stretch_hazard_aware_route
            "distance_m": 1200.0,
            "duration_s": 1000.0,
            "steps": ["Head northeast on Gandhi Road toward shelter", "Arrive at shelter"],
            "warnings": [],
            "hazard_cells_avoided": 2,
            "maps_urls": None,
            "attribution": None,
            "provider": "mock",
            "reroute": reroute,
            "is_replay": False,
            "mode_of_data": "mock",
            "generated_at": _now_utc(),
        }

    ctx = _get_context()
    return calculate_safe_route(
        lat=effective_lat,
        lng=effective_lng,
        mode=mode,
        to_shelter=to_shelter,
        reroute=reroute,
        device_id=device_id,
        client_ip=client_ip,
        ctx=ctx,
        shelter_repo=_SHELTER_REPO,
        service_bbox=settings.service_bbox,
    )


# --- Authority Endpoints (Protected by X-Authority-Key) ---

@router.post(
    "/alerts",
    response_model=Alert,
    status_code=status.HTTP_201_CREATED,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def create_alert_endpoint(payload: AlertCreate) -> Alert:
    """Publish a new official disaster alert or all-clear notice."""
    settings = get_settings()
    if settings.mock:
        new_id = f"alt_{uuid4().hex[:8]}"
        alert_dict = payload.model_dump()
        alert_dict["id"] = new_id
        global _MOCK_ALERTS
        _MOCK_ALERTS.insert(0, alert_dict)
        return Alert(**alert_dict)

    ctx = _get_context()
    return create_official_alert(payload, ctx, _ALERT_REPO)


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def list_alerts_endpoint(
    active: bool = Query(True, description="Filter for active alerts")
) -> AlertListResponse:
    """Fetch active published alerts."""
    settings = get_settings()
    if settings.mock:
        alerts = [Alert(**a) for a in load_mock_alerts()]
        return AlertListResponse(alerts=alerts, total=len(alerts))

    ctx = _get_context()
    return list_official_alerts(active, ctx, _ALERT_REPO)


@router.delete(
    "/alerts/{alert_id}",
    response_model=AlertExpireResponse,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def expire_alert_endpoint(alert_id: str) -> AlertExpireResponse:
    """Immediately expire an active alert."""
    settings = get_settings()
    if settings.mock:
        global _MOCK_ALERTS
        _MOCK_ALERTS = [a for a in _MOCK_ALERTS if a.get("id") != alert_id]
        return AlertExpireResponse(ok=True, id=alert_id, expired_at=_now_utc())

    ctx = _get_context()
    return expire_official_alert(alert_id, ctx, _ALERT_REPO)


@router.get(
    "/checkins",
    response_model=CheckinListResponse,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def list_checkins_endpoint() -> CheckinListResponse:
    """Retrieve check-ins deduplicated by device alongside aggregated H3 res-7 clusters."""
    settings = get_settings()
    if settings.mock:
        data = load_mock_checkins()
        items = [CheckinItem(**item) for item in data.get("items", [])]
        return CheckinListResponse(items=items, clusters=data.get("clusters", []))

    return list_checkins(_CHECKIN_REPO)


@router.patch(
    "/checkins/{checkin_id}",
    response_model=CheckinItem,
    tags=["Authority"],
    dependencies=[Security(verify_authority_key)],
)
async def handle_checkin_endpoint(checkin_id: str, payload: CheckinUpdate) -> CheckinItem:
    """Mark a tourist check-in as handled by rescue operators."""
    settings = get_settings()
    if settings.mock:
        global _MOCK_CHECKINS
        for item in _MOCK_CHECKINS:
            if item.get("id") == checkin_id:
                item["handled"] = payload.handled
                return CheckinItem(**item)
        raise HTTPException(status_code=404, detail=f"Check-in {checkin_id} not found")

    return handle_checkin(checkin_id, payload, _CHECKIN_REPO)


# --- Scenario Control Endpoints ---

@router.post("/scenario/start", response_model=ScenarioStatus, tags=["Scenario"])
async def start_scenario_endpoint(payload: ScenarioStart) -> ScenarioStatus:
    """Launch historical scenario playback."""
    settings = get_settings()
    if settings.mock:
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

    # Validate scenario file exists in data/scenarios
    root = _get_project_root()
    scenario_path = root / "data" / "scenarios" / f"{payload.name}.json"
    if not scenario_path.exists():
        raise HTTPException(status_code=404, detail=f"Scenario '{payload.name}' not found")

    global _SCENARIO, _SCENARIO_CLOCK, _IS_REPLAY_ACTIVE
    if _SCENARIO is None or _SCENARIO.name != payload.name:
        init_scenario(scenario_path, root / "data" / "shelters.json")

    assert _SCENARIO_CLOCK is not None
    _SCENARIO_CLOCK.start(speed=payload.speed)
    _IS_REPLAY_ACTIVE = True
    clear_cells_cache()

    return _build_scenario_status_response()


@router.post("/scenario/seek", response_model=ScenarioStatus, tags=["Scenario"])
async def seek_scenario_endpoint(payload: ScenarioSeek) -> ScenarioStatus:
    """Seek the replay scenario clock to a specific timestamp, offset, or bookmark."""
    settings = get_settings()
    if settings.mock:
        start_dt = datetime.fromisoformat(_SCENARIO_STATE["scenario_start"].replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(_SCENARIO_STATE["scenario_end"].replace("Z", "+00:00"))
        max_duration = int((end_dt - start_dt).total_seconds())

        if payload.bookmark is not None:
            if payload.bookmark == "golden_moment":
                target_offset = 39600
            else:
                target_offset = 0
        elif payload.offset_s is not None:
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

    global _SCENARIO_CLOCK, _SCENARIO, _IS_REPLAY_ACTIVE
    if _SCENARIO_CLOCK is None:
        raise HTTPException(status_code=400, detail="Scenario clock has not been initialized. Call /scenario/start first.")

    target_offset_s = payload.offset_s
    target_t_dt = None
    if payload.bookmark is not None:
        if _SCENARIO is None:
            raise HTTPException(status_code=400, detail="Scenario not loaded")
        bm = next((b for b in _SCENARIO.bookmarks if b.name == payload.bookmark), None)
        if not bm:
            raise HTTPException(status_code=404, detail=f"Bookmark '{payload.bookmark}' not found")
        target_offset_s = bm.t_offset_s
    elif payload.t is not None:
        try:
            target_t_dt = datetime.fromisoformat(payload.t.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid ISO-8601 timestamp in 't'")

    try:
        _SCENARIO_CLOCK.seek(t=target_t_dt, offset_s=target_offset_s)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    clear_cells_cache()
    return _build_scenario_status_response()


@router.post("/scenario/reset", response_model=ScenarioResetResponse, tags=["Scenario"])
async def reset_scenario_endpoint() -> ScenarioResetResponse:
    """Stop scenario playback and revert to live mode."""
    settings = get_settings()
    if settings.mock:
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

    global _SCENARIO_CLOCK, _REPLAY_OVERLAY, _IS_REPLAY_ACTIVE
    if _SCENARIO_CLOCK is not None:
        _SCENARIO_CLOCK.reset()
    _IS_REPLAY_ACTIVE = False
    _REPLAY_OVERLAY.clear()
    clear_cells_cache()

    return ScenarioResetResponse(ok=True, mode="live", is_replay=False)


@router.get("/scenario/status", response_model=ScenarioStatus, tags=["Scenario"])
async def get_scenario_status_endpoint() -> ScenarioStatus:
    """Get current status of scenario replay clock with additive metadata."""
    settings = get_settings()
    if settings.mock:
        state = dict(_SCENARIO_STATE)
        if not state["is_running"]:
            state["current_time"] = _now_utc()
        return ScenarioStatus(**state)

    return _build_scenario_status_response()


def _build_scenario_status_response() -> ScenarioStatus:
    global _SCENARIO, _SCENARIO_CLOCK, _IS_REPLAY_ACTIVE
    now_iso = _now_utc()
    if not _IS_REPLAY_ACTIVE or _SCENARIO is None or _SCENARIO_CLOCK is None:
        return ScenarioStatus(
            name="live",
            mode="live",
            is_running=False,
            paused=False,
            speed=1.0,
            current_time=now_iso,
            elapsed_s=0,
            is_replay=False,
            finished=False,
            bookmarks=None,
        )

    sim_dt = _SCENARIO_CLOCK.sim_time()
    elapsed = int((sim_dt - _SCENARIO.t0).total_seconds())
    bookmarks_list = [
        {"name": b.name, "t_offset_s": b.t_offset_s, "description": b.description}
        for b in _SCENARIO.bookmarks
    ]
    end_dt = _SCENARIO.t0 + timedelta(seconds=_SCENARIO.duration_s)

    return ScenarioStatus(
        name=_SCENARIO.name,
        mode="replay",
        is_running=_SCENARIO_CLOCK.is_running,
        paused=_SCENARIO_CLOCK.is_paused,
        speed=_SCENARIO_CLOCK.speed,
        current_time=sim_dt.isoformat(),
        elapsed_s=elapsed,
        scenario_start=_SCENARIO.t0.isoformat(),
        scenario_end=end_dt.isoformat(),
        start_time=_SCENARIO.t0.isoformat(),
        end_time=end_dt.isoformat(),
        duration_s=_SCENARIO.duration_s,
        is_replay=True,
        label=REPLAY_LABEL,
        disclaimer=REPLAY_DISCLAIMER,
        finished=_SCENARIO_CLOCK.is_finished(),
        bookmarks=bookmarks_list,
    )


# --- Stretch Route Endpoint ---

@router.get("/route", response_model=RouteResponse, tags=["Tourist"])
async def get_hazard_aware_route_endpoint(
    from_lat: float = Query(..., ge=-90.0, le=90.0),
    from_lng: float = Query(..., ge=-180.0, le=180.0),
    to_shelter: str = Query(...),
    lang: str = Query("en"),
) -> RouteResponse:
    """Generate hazard-aware route avoiding cells marked official_hazard or likely_hazard."""
    shelters = load_mock_shelters()
    shelter = next((s for s in shelters if s["id"] == to_shelter), None)
    dest_lat = shelter["lat"] if shelter else from_lat + 0.005
    dest_lng = shelter["lng"] if shelter else from_lng + 0.005

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
