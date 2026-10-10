"""Hazard-aware safe route calculation service with caching and fallbacks."""

import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException

from backend.app.geo import geojson_polygon_to_cells, latlng_to_cell
from backend.app.services.state_service import is_cell_in_service_bbox
from backend.app.trust import assess_cells
from backend.app.repositories import ShelterRepo
from backend.app.routing.avoid import build_avoid_set, build_direct_line_route
from backend.app.routing.destinations import is_shelter_safe, select_safe_destinations
from backend.app.routing.maps_urls import generate_maps_urls
from backend.app.routing.types import (
    DEFAULT_ORS_ATTRIBUTION,
    ROUTE_WARNING_DETAILS,
    AvoidSetResult,
    MapsUrls,
    RouteKindEnum,
    RouteResponse,
    RouteResult,
    RouteWarningEnum,
    RouteWarningItem,
    SafeDestination,
    StructuredStep,
)
from backend.app.routing.ors_adapter import OpenRouteServiceAdapter
from backend.app.services.context import DataContext

_DEFAULT_ORS_ADAPTER = OpenRouteServiceAdapter()


def get_ors_adapter() -> OpenRouteServiceAdapter:
    """Return singleton OpenRouteServiceAdapter instance."""
    return _DEFAULT_ORS_ADAPTER


# In-memory LRU route cache: (key) -> (RouteResponse, expires_at_timestamp)
_ROUTE_CACHE: OrderedDict[Tuple[Any, ...], Tuple[RouteResponse, float]] = OrderedDict()
_MAX_ROUTE_CACHE_ENTRIES = 500
_ROUTE_CACHE_TTL_SECONDS = 900.0  # 15 minutes

# In-memory per-client request limiter: client_id -> list of timestamps
_CLIENT_TIMESTAMPS: Dict[str, List[float]] = {}
_PER_CLIENT_LIMIT = 30
_PER_CLIENT_WINDOW_S = 60.0


def clear_route_cache() -> None:
    """Clear all in-memory route cache entries."""
    _ROUTE_CACHE.clear()


def check_route_rate_limit(client_id: str) -> None:
    """Enforce per-client 30 requests/minute limit."""
    now = time.time()
    timestamps = _CLIENT_TIMESTAMPS.get(client_id, [])
    # Keep only timestamps within window
    timestamps = [t for t in timestamps if now - t < _PER_CLIENT_WINDOW_S]
    if len(timestamps) >= _PER_CLIENT_LIMIT:
        oldest = timestamps[0]
        retry_after = max(1, int(_PER_CLIENT_WINDOW_S - (now - oldest)))
        _CLIENT_TIMESTAMPS[client_id] = timestamps
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded: maximum 30 route requests per minute.",
            headers={"Retry-After": str(retry_after)},
        )
    timestamps.append(now)
    _CLIENT_TIMESTAMPS[client_id] = timestamps


async def calculate_safe_route(
    lat: float,
    lng: float,
    mode: str,
    to_shelter: Optional[str],
    reroute: bool,
    device_id: Optional[str],
    client_ip: str,
    ctx: DataContext,
    shelter_repo: ShelterRepo,
    service_bbox: str = "80.10,12.80,80.40,13.30",
    ors_adapter: Optional[OpenRouteServiceAdapter] = None,
) -> RouteResponse:
    """Calculate an emergency hazard-aware route to safety."""
    # 1. Validate coordinates
    if not (-90.0 <= lat <= 90.0):
        raise HTTPException(status_code=422, detail=f"Latitude {lat} out of range [-90.0, 90.0]")
    if not (-180.0 <= lng <= 180.0):
        raise HTTPException(status_code=422, detail=f"Longitude {lng} out of range [-180.0, 180.0]")
    if mode not in ("walk", "drive"):
        raise HTTPException(status_code=422, detail=f"Invalid mode '{mode}'. Must be 'walk' or 'drive'.")

    # 2. Rate limiting (per device_id or per client IP)
    rate_limit_key = device_id or client_ip
    check_route_rate_limit(rate_limit_key)

    # 3. Check LRU cache (if not reroute)
    cache_key = (
        round(lat, 4),
        round(lng, 4),
        mode,
        to_shelter,
        ctx.is_replay,
        int(ctx.now.timestamp() // 300),  # 5-min bucket
    )
    if not reroute and cache_key in _ROUTE_CACHE:
        cached_resp, expires_at = _ROUTE_CACHE[cache_key]
        if time.time() < expires_at:
            _ROUTE_CACHE.move_to_end(cache_key)
            return cached_resp

    now_iso = ctx.now.isoformat()
    valid_until_iso = (ctx.now + timedelta(minutes=15)).isoformat()
    route_id = f"rt_{uuid4().hex[:12]}"

    # 4. Service coverage boundary check
    origin_cell = latlng_to_cell(lat, lng, 8)
    if not is_cell_in_service_bbox(origin_cell, service_bbox):
        outside_warning = RouteWarningItem(
            key=RouteWarningEnum.OUTSIDE_COVERAGE.value,
            detail=ROUTE_WARNING_DETAILS[RouteWarningEnum.OUTSIDE_COVERAGE.value],
        )
        return RouteResponse(
            route_id=route_id,
            route_version=1,
            valid_until=valid_until_iso,
            kind=RouteKindEnum.NONE,
            destination=None,
            alternatives=[],
            geometry=None,
            distance_m=0.0,
            duration_s=None,
            steps=[],
            warnings=[outside_warning],
            hazard_cells_avoided=0,
            maps_urls=None,
            attribution=None,
            provider=None,
            reroute=reroute,
            reason_hint=None,
            is_replay=ctx.is_replay,
            mode_of_data=ctx.mode,
            generated_at=now_iso,
        )

    # 5. Evaluate assessments by cell
    cells_to_eval = {origin_cell}
    # Add shelter cells
    all_shelters = shelter_repo.list_all()
    for s in all_shelters:
        cells_to_eval.add(latlng_to_cell(s.lat, s.lng, 8))
    # Add cells from active official alerts
    for a in ctx.alerts:
        try:
            poly_cells = geojson_polygon_to_cells(a.area.model_dump(), 8)
            cells_to_eval.update(poly_cells)
        except Exception:
            pass
    # Add cells with crowd reports
    cells_to_eval.update(ctx.reports_by_cell.keys())

    eval_list = list(cells_to_eval)
    features_by_cell = {c: ctx.features_provider(c) for c in eval_list}
    assessments_by_cell = assess_cells(
        cells=eval_list,
        features_by_cell=features_by_cell,
        reports_by_cell=ctx.reports_by_cell,
        alerts=ctx.alerts,
        now=ctx.now,
    )

    # 6. Safe destination selection
    all_shelters = shelter_repo.list_all()
    shelter_dicts = [
        {
            "id": s.id,
            "name": s.name,
            "name_local": s.name_local,
            "lat": s.lat,
            "lng": s.lng,
            "open": s.open,
            "is_demo": getattr(s, "is_demo", True),
        }
        for s in all_shelters
    ]

    safe_destinations = select_safe_destinations(lat, lng, shelter_dicts, assessments_by_cell, limit=3)
    warnings: List[RouteWarningItem] = []

    chosen_destination: Optional[SafeDestination] = None
    alternatives: List[SafeDestination] = []

    if to_shelter:
        # User explicitly requested a specific shelter
        target = next((s for s in shelter_dicts if s["id"] == to_shelter), None)
        if target:
            is_safe, cell, status = is_shelter_safe(target["lat"], target["lng"], assessments_by_cell)
            chosen_destination = SafeDestination(
                shelter_id=target["id"],
                id=target["id"],
                name=target["name"],
                name_local=target.get("name_local") or target["name"],
                lat=target["lat"],
                lng=target["lng"],
                distance_m=0.0,
                bearing_deg=0.0,
                compass_direction="N",
                cell=cell,
                status=status,
                is_safe=is_safe,
            )
            if not is_safe:
                warnings.append(
                    RouteWarningItem(
                        key=RouteWarningEnum.DESTINATION_IN_HAZARD.value,
                        detail=ROUTE_WARNING_DETAILS[RouteWarningEnum.DESTINATION_IN_HAZARD.value],
                    )
                )
            # Alternatives: other safe destinations
            alternatives = [s for s in safe_destinations if s.shelter_id != to_shelter][:2]
        else:
            raise HTTPException(status_code=404, detail=f"Shelter '{to_shelter}' not found.")
    else:
        if safe_destinations:
            chosen_destination = safe_destinations[0]
            alternatives = safe_destinations[1:3]
        else:
            warnings.append(
                RouteWarningItem(
                    key=RouteWarningEnum.SHELTER_UNREACHABLE.value,
                    detail=ROUTE_WARNING_DETAILS[RouteWarningEnum.SHELTER_UNREACHABLE.value],
                )
            )

    if chosen_destination is None:
        # No reachable shelter
        return RouteResponse(
            route_id=route_id,
            route_version=1,
            valid_until=valid_until_iso,
            kind=RouteKindEnum.NONE,
            destination=None,
            alternatives=[],
            geometry=None,
            distance_m=0.0,
            duration_s=None,
            steps=[],
            warnings=warnings,
            hazard_cells_avoided=0,
            maps_urls=None,
            attribution=None,
            provider=None,
            reroute=reroute,
            reason_hint=None,
            is_replay=ctx.is_replay,
            mode_of_data=ctx.mode,
            generated_at=now_iso,
        )

    # 7. Build avoid set
    avoid_set = build_avoid_set(lat, lng, chosen_destination.lat, chosen_destination.lng, assessments_by_cell)
    for w in avoid_set.warnings:
        warnings.append(RouteWarningItem(key=w.value, detail=ROUTE_WARNING_DETAILS.get(w.value, w.value)))

    # 8. Attempt road route from provider adapter
    adapter = ors_adapter or _DEFAULT_ORS_ADAPTER
    road_route: Optional[RouteResult] = None
    if adapter.is_available:
        try:
            road_route = await adapter.get_directions(
                origin_lat=lat,
                origin_lng=lng,
                dest_lat=chosen_destination.lat,
                dest_lng=chosen_destination.lng,
                profile=mode,
                avoid_set=avoid_set,
            )
        except Exception:
            pass

    maps_urls = generate_maps_urls(lat, lng, chosen_destination.lat, chosen_destination.lng, mode=mode)

    if road_route and road_route.kind == RouteKindEnum.ROAD_ROUTE:
        for w in road_route.warnings:
            warnings.append(RouteWarningItem(key=w.value, detail=ROUTE_WARNING_DETAILS.get(w.value, w.value)))
        route_kind = RouteKindEnum.ROAD_ROUTE
        route_geom = road_route.geometry
        route_dist = road_route.distance_m
        route_duration = road_route.duration_s
        route_steps = road_route.steps
        hazard_avoided = road_route.hazard_cells_avoided
        attribution = road_route.attribution
        provider_name = road_route.provider
    else:
        # Fall back to direct line
        warnings.append(
            RouteWarningItem(
                key=RouteWarningEnum.ROUTING_UNAVAILABLE.value,
                detail=ROUTE_WARNING_DETAILS[RouteWarningEnum.ROUTING_UNAVAILABLE.value],
            )
        )
        direct_line = build_direct_line_route(lat, lng, chosen_destination.lat, chosen_destination.lng)
        route_kind = RouteKindEnum.DIRECT_LINE
        route_geom = direct_line.geometry
        route_dist = direct_line.distance_m
        route_duration = direct_line.duration_s
        route_steps = direct_line.steps
        hazard_avoided = 0
        attribution = None
        provider_name = "direct_line"

    # Deduplicate warning keys
    seen_keys = set()
    deduped_warnings = []
    for item in warnings:
        if item.key not in seen_keys:
            seen_keys.add(item.key)
            deduped_warnings.append(item)

    response = RouteResponse(
        route_id=route_id,
        route_version=1,
        valid_until=valid_until_iso,
        kind=route_kind,
        destination=chosen_destination,
        alternatives=alternatives,
        geometry=route_geom,
        distance_m=route_dist,
        duration_s=route_duration,
        steps=route_steps,
        warnings=deduped_warnings,
        hazard_cells_avoided=hazard_avoided,
        maps_urls=maps_urls,
        attribution=attribution,
        provider=provider_name,
        reroute=reroute,
        reason_hint=None,
        is_replay=ctx.is_replay,
        mode_of_data=ctx.mode,
        generated_at=now_iso,
    )

    # Store in LRU cache
    if len(_ROUTE_CACHE) >= _MAX_ROUTE_CACHE_ENTRIES:
        _ROUTE_CACHE.popitem(last=False)
    _ROUTE_CACHE[cache_key] = (response, time.time() + _ROUTE_CACHE_TTL_SECONDS)

    return response
