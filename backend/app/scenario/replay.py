"""Pure functional replay state projection, spatial feature lookup, and in-memory overlay."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from shapely.geometry import Point, Polygon
from shapely.prepared import prep

from backend.app.geo import cell_to_latlng
from backend.app.ingest.lifecycle import get_active_alerts
from backend.app.models.alert import Alert
from backend.app.scenario.types import AreaGroup, ReplayInputs, Scenario
from backend.app.trust.types import CellFeatures, Report

# Global spatial caches for prepared geometries
_FLOOD_PRONE_POLYS: Optional[List[Any]] = None
_GROUP_POLY_CACHE: Dict[str, Tuple[Polygon, Any]] = {}
_CACHE_LOCK = threading.Lock()


def _ensure_flood_prone_cache(geojson_path: Optional[Union[Path, str]] = None) -> List[Any]:
    """Load and cache prepared flood-prone polygons from data/flood_prone.geojson."""
    global _FLOOD_PRONE_POLYS
    if _FLOOD_PRONE_POLYS is not None:
        return _FLOOD_PRONE_POLYS

    with _CACHE_LOCK:
        if _FLOOD_PRONE_POLYS is not None:
            return _FLOOD_PRONE_POLYS

        p = Path(geojson_path) if geojson_path else Path(__file__).resolve().parent.parent.parent.parent / "data" / "flood_prone.geojson"
        if not p.exists():
            _FLOOD_PRONE_POLYS = []
            return _FLOOD_PRONE_POLYS

        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        prepared_list = []
        for feat in data.get("features", []):
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates")
            if geom.get("type") == "Polygon" and coords and coords[0]:
                poly = Polygon(coords[0])
                if poly.is_valid and not poly.is_empty:
                    prepared_list.append(prep(poly))

        _FLOOD_PRONE_POLYS = prepared_list
        return _FLOOD_PRONE_POLYS


def _get_prepared_group(group: AreaGroup) -> Tuple[Polygon, Any]:
    """Get or build cached (Polygon, prepared_polygon) for an area group."""
    with _CACHE_LOCK:
        cached = _GROUP_POLY_CACHE.get(group.id)
        if cached is not None:
            return cached

        exterior = group.polygon.coordinates[0]
        poly = Polygon(exterior)
        prepped = prep(poly)
        _GROUP_POLY_CACHE[group.id] = (poly, prepped)
        return poly, prepped


def is_point_flood_prone(lng: float, lat: float, geojson_path: Optional[Union[Path, str]] = None) -> bool:
    """Check if point [lng, lat] falls inside any prepared flood-prone polygon."""
    prepared_polys = _ensure_flood_prone_cache(geojson_path)
    pt = Point(lng, lat)
    for prepped in prepared_polys:
        if prepped.contains(pt):
            return True
    return False


def interpolate_group_rain(group: AreaGroup, t_offset_s: float) -> Tuple[float, float]:
    """Linearly interpolate (rain_mm_3h, rain_mm_24h) from group keyframes at offset."""
    kfs = group.keyframes
    if not kfs:
        return 0.0, 0.0

    if t_offset_s <= kfs[0].t_offset_s:
        return kfs[0].rain_mm_3h, kfs[0].rain_mm_24h
    if t_offset_s >= kfs[-1].t_offset_s:
        return kfs[-1].rain_mm_3h, kfs[-1].rain_mm_24h

    # Find interval [k1, k2]
    for i in range(len(kfs) - 1):
        k1 = kfs[i]
        k2 = kfs[i + 1]
        if k1.t_offset_s <= t_offset_s <= k2.t_offset_s:
            span = k2.t_offset_s - k1.t_offset_s
            if span <= 0:
                return k1.rain_mm_3h, k1.rain_mm_24h
            frac = (t_offset_s - k1.t_offset_s) / span
            r3 = k1.rain_mm_3h + frac * (k2.rain_mm_3h - k1.rain_mm_3h)
            r24 = k1.rain_mm_24h + frac * (k2.rain_mm_24h - k1.rain_mm_24h)
            return r3, r24

    return kfs[-1].rain_mm_3h, kfs[-1].rain_mm_24h


def features_for_cell(scenario: Scenario, cell: str, t: datetime) -> CellFeatures:
    """Pure lookup of meteorological and terrain features for an H3 cell at time t.
    
    Rules:
    1. Cell centre [lng, lat] point-in-polygon against cached area group polygons.
    2. Cells outside every group return rain_available=False (engine says unverified, never contradicted).
    3. Inside group: linearly interpolate rain_mm_3h and rain_mm_24h from group keyframes; rain_available=True.
    4. flood_prone evaluated by cell centre inside prepared flood_prone polygons.
    """
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    else:
        t = t.astimezone(timezone.utc)

    lat, lng = cell_to_latlng(cell)
    pt = Point(lng, lat)

    # 1. Check terrain vulnerability
    flood_prone = is_point_flood_prone(lng, lat)

    # 2. Check area group membership
    matched_group: Optional[AreaGroup] = None
    for group in scenario.area_groups:
        _, prepped = _get_prepared_group(group)
        if prepped.contains(pt):
            matched_group = group
            break

    if matched_group is None:
        # Cell outside all modeled scenario groups -> rain data unavailable
        return CellFeatures(
            rain_mm_3h=0.0,
            rain_mm_24h=0.0,
            flood_prone=flood_prone,
            rain_available=False,
        )

    # Inside group -> compute elapsed seconds from scenario start and interpolate
    t_offset_s = (t - scenario.t0).total_seconds()
    r3, r24 = interpolate_group_rain(matched_group, t_offset_s)

    return CellFeatures(
        rain_mm_3h=r3,
        rain_mm_24h=r24,
        flood_prone=flood_prone,
        rain_available=True,
    )


class ReplayOverlay:
    """In-memory collection of dynamic user reports submitted during replay.
    
    Guarantees:
    - Thread-safe ring buffer: bounded size 1000 (drops oldest when capacity exceeded).
    - Cleared on clock start or reset (seek preserves overlay).
    - Pure point-in-time filtering: get_reports_at(t) returns reports with created_at <= t.
    """

    MAX_REPORTS: int = 1000

    def __init__(self) -> None:
        self._reports: List[Report] = []
        self._lock = threading.Lock()

    def add_report(self, report: Report) -> None:
        """Add dynamic report, dropping oldest if capacity exceeded."""
        with self._lock:
            if len(self._reports) >= self.MAX_REPORTS:
                self._reports.pop(0)
            self._reports.append(report)

    def get_reports_at(self, t: datetime) -> List[Report]:
        """Return all overlay reports with created_at <= t."""
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        else:
            t = t.astimezone(timezone.utc)

        with self._lock:
            return [r for r in self._reports if r.created_at <= t]

    def clear(self) -> None:
        """Clear all overlay reports."""
        with self._lock:
            self._reports.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._reports)


def scenario_inputs_at(
    scenario: Scenario,
    t: datetime,
    overlay: Optional[ReplayOverlay] = None,
) -> ReplayInputs:
    """Pure point-in-time projection of scenario inputs at simulated time t.
    
    Guarantees:
    - Pure function of (scenario, t): seeking backward or forward yields identical results.
    - Active alerts determined by temporal window and supersede lifecycle logic.
    - Reports: scenario reports with created_at <= t, plus overlay reports with created_at <= t.
    - features_for_cell: bound pure lookup function for the given scenario and time t.
    """
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    else:
        t = t.astimezone(timezone.utc)

    # 1. Active alerts via lifecycle logic
    active_alerts = get_active_alerts(scenario.alerts, t)

    # 2. Scenario reports up to time t
    active_reports = [r for r in scenario.reports if r.created_at <= t]

    # 3. Add overlay reports if provided
    if overlay is not None:
        active_reports.extend(overlay.get_reports_at(t))

    def _features_fn(cell: str, eval_time: Optional[datetime] = None) -> CellFeatures:
        return features_for_cell(scenario, cell, eval_time or t)

    return ReplayInputs(
        alerts=active_alerts,
        reports=active_reports,
        features_for_cell=_features_fn,
    )
