"""H3 cell batch assessment service with GeoJSON serialization and TTL polling cache."""

import time
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException

from backend.app.geo import cell_to_geojson_boundary, cells_in_bbox
from backend.app.models import CellFeature, CellFeatureCollection, GeoJSONPolygon
from backend.app.services.context import DataContext
from backend.app.trust import assess_cells

# Explicit named constants documented for system limits
MAX_BBOX_DELTA: float = 0.3  # Max degrees span per side
MAX_BBOX_CELLS: int = 3000   # Max H3 resolution-8 cells evaluated in a single request
CACHE_TTL_SECONDS: float = 5.0  # 5-second polling protection cache

# In-memory TTL cache: key -> (cached_time, CellFeatureCollection)
_CELLS_CACHE: Dict[Tuple[str, float, float, float, float], Tuple[float, CellFeatureCollection]] = {}


def clear_cells_cache() -> None:
    """Clear all cached cell evaluation responses immediately.

    Must be invoked on any state mutation:
    - New or expired official alerts
    - New crowd reports
    - Scenario playback start, seek, or reset
    - Operating mode switch
    """
    global _CELLS_CACHE
    _CELLS_CACHE.clear()


def parse_bbox_string(bbox_str: str) -> Tuple[float, float, float, float]:
    """Parse and validate bounding box in lng,lat order: min_lng,min_lat,max_lng,max_lat.

    Raises HTTPException 422 if malformed, out of geographic bounds, or inverted.
    """
    try:
        parts = [float(p.strip()) for p in bbox_str.split(",")]
    except Exception:
        raise HTTPException(status_code=422, detail="Malformed bounding box: must be four comma-separated floats.")

    if len(parts) != 4:
        raise HTTPException(
            status_code=422,
            detail=f"Malformed bounding box: expected 4 coordinates (minLng,minLat,maxLng,maxLat), got {len(parts)}.",
        )

    min_lng, min_lat, max_lng, max_lat = parts

    # Range validation
    if not (-180.0 <= min_lng <= 180.0 and -180.0 <= max_lng <= 180.0):
        raise HTTPException(status_code=422, detail="Bounding box longitudes out of range [-180.0, 180.0].")
    if not (-90.0 <= min_lat <= 90.0 and -90.0 <= max_lat <= 90.0):
        raise HTTPException(status_code=422, detail="Bounding box latitudes out of range [-90.0, 90.0].")

    if min_lng > max_lng:
        raise HTTPException(status_code=422, detail="Invalid bounding box: minLng cannot be greater than maxLng.")
    if min_lat > max_lat:
        raise HTTPException(status_code=422, detail="Invalid bounding box: minLat cannot be greater than maxLat.")

    # Dimension delta cap validation (0.3 degrees)
    delta_lng = max_lng - min_lng
    delta_lat = max_lat - min_lat
    if delta_lng > MAX_BBOX_DELTA or delta_lat > MAX_BBOX_DELTA:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Bounding box dimension ({delta_lng:.3f}x{delta_lat:.3f} deg) exceeds "
                f"maximum allowable delta of {MAX_BBOX_DELTA} degrees per side."
            ),
        )

    return min_lng, min_lat, max_lng, max_lat


def get_cells_for_bbox(bbox_str: str, ctx: DataContext) -> CellFeatureCollection:
    """Evaluate all H3 cells intersecting the bounding box with TTL caching and batch trust engine."""
    min_lng, min_lat, max_lng, max_lat = parse_bbox_string(bbox_str)

    # Rounded cache key: (mode, rounded_min_lng, rounded_min_lat, rounded_max_lng, rounded_max_lat)
    cache_key = (
        ctx.mode,
        round(min_lng, 3),
        round(min_lat, 3),
        round(max_lng, 3),
        round(max_lat, 3),
    )

    now_wall = time.time()
    if cache_key in _CELLS_CACHE:
        cached_time, cached_collection = _CELLS_CACHE[cache_key]
        if now_wall - cached_time < CACHE_TTL_SECONDS:
            return cached_collection

    # Compute cells in bounding box at resolution 8
    try:
        cells = list(cells_in_bbox(min_lng, min_lat, max_lng, max_lat, res=8))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Cell count cap validation (3,000 cells)
    if len(cells) > MAX_BBOX_CELLS:
        raise HTTPException(
            status_code=422,
            detail=f"Requested bounding box contains {len(cells)} cells, exceeding cap of {MAX_BBOX_CELLS} cells.",
        )

    # Batch evaluate cells through Bayesian trust engine
    features_by_cell = {c: ctx.features_provider(c) for c in cells}
    assessments = assess_cells(
        cells=cells,
        features_by_cell=features_by_cell,
        reports_by_cell=ctx.reports_by_cell,
        alerts=ctx.alerts,
        now=ctx.now,
    )

    # Construct GeoJSON FeatureCollection
    updated_at_iso = ctx.now.isoformat()
    features_list: List[CellFeature] = []

    for c in sorted(cells):
        asm = assessments[c]
        # Coordinates rounded strictly to 5 decimals per specification
        raw_ring = cell_to_geojson_boundary(c)
        rounded_ring = [[round(pt[0], 5), round(pt[1], 5)] for pt in raw_ring]
        if rounded_ring and rounded_ring[0] != rounded_ring[-1]:
            rounded_ring.append(rounded_ring[0])

        polygon_geom = GeoJSONPolygon(type="Polygon", coordinates=[rounded_ring])

        feat = CellFeature(
            type="Feature",
            id=c,
            geometry=polygon_geom,
            properties={
                "cell": c,
                "status": asm.status,
                "p_hazard": round(asm.p_hazard, 4),
                "updated_at": updated_at_iso,
            },
        )
        features_list.append(feat)

    collection = CellFeatureCollection(type="FeatureCollection", features=features_list)

    # Store in short TTL cache
    _CELLS_CACHE[cache_key] = (now_wall, collection)
    return collection
