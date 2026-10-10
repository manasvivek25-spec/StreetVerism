"""Hazard avoid set geometry construction, corridor pruning, and direct-line fallbacks."""

import math
from typing import Any, Dict, List, Optional, Set, Tuple
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, mapping
from shapely.ops import unary_union

from backend.app.geo.h3_utils import (
    cell_to_geojson_boundary,
    cell_to_latlng,
    grid_disk,
    haversine_distance_m,
    latlng_to_cell,
)
from backend.app.routing.types import (
    AvoidSetResult,
    ManeuverEnum,
    RouteKindEnum,
    RouteResult,
    RouteWarningEnum,
    StructuredStep,
)

# OpenRouteService official limit constraints (verified from official documentation)
ORS_MAX_AVOID_AREA_KM2 = 200.0
ORS_MAX_AVOID_EXTENT_KM = 20.0
ORS_MAX_AVOID_VERTICES = 200

# Default corridor search buffer (~3.3 km in latitude degrees)
DEFAULT_CORRIDOR_BUFFER_DEG = 0.03


def _count_vertices(geom: Any) -> int:
    """Count total boundary vertices across Polygon or MultiPolygon."""
    if geom is None or geom.is_empty:
        return 0
    if isinstance(geom, Polygon):
        count = len(geom.exterior.coords)
        for interior in geom.interiors:
            count += len(interior.coords)
        return count
    if isinstance(geom, MultiPolygon):
        return sum(_count_vertices(poly) for poly in geom.geoms)
    return 0


def _calculate_geom_area_km2(geom: Any) -> float:
    """Calculate approximate area in km² from longitude/latitude degree geometry."""
    if geom is None or geom.is_empty:
        return 0.0
    min_x, min_y, max_x, max_y = geom.bounds
    mean_lat = (min_y + max_y) / 2.0
    # 1 degree of latitude ≈ 111.139 km
    km_per_deg_lat = 111.139
    # 1 degree of longitude ≈ 111.139 * cos(lat) km
    km_per_deg_lng = 111.139 * math.cos(math.radians(mean_lat))
    area_km2 = geom.area * (km_per_deg_lat * km_per_deg_lng)
    return round(area_km2, 3)


def _calculate_geom_extent_km(geom: Any) -> float:
    """Calculate maximum bounding box extent (width or height) in kilometers."""
    if geom is None or geom.is_empty:
        return 0.0
    min_lng, min_lat, max_lng, max_lat = geom.bounds
    center_lat = (min_lat + max_lat) / 2.0
    center_lng = (min_lng + max_lng) / 2.0

    width_km = haversine_distance_m(center_lat, min_lng, center_lat, max_lng) / 1000.0
    height_km = haversine_distance_m(min_lat, center_lng, max_lat, center_lng) / 1000.0
    return round(max(width_km, height_km), 3)


def build_avoid_set(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    assessments_by_cell: Dict[str, Any],
    max_area_km2: float = ORS_MAX_AVOID_AREA_KM2,
    max_extent_km: float = ORS_MAX_AVOID_EXTENT_KM,
    max_vertices: int = ORS_MAX_AVOID_VERTICES,
    pad_deg: float = DEFAULT_CORRIDOR_BUFFER_DEG,
) -> AvoidSetResult:
    """Build unified avoid geometry for hazardous cells respecting provider limits.
    
    Rules & Constraints:
    1. Origin cell and origin's k=1 disk are excluded from avoid set.
    2. Destination cell is excluded from avoid set.
    3. Cells with official_hazard or likely_hazard are candidate avoid cells.
    4. Cells with unverified reports are NEVER avoided, but if any unverified cell
       is near the travel corridor (within pad_deg), emits unverified_reports_nearby warning.
    5. If candidate union exceeds area, extent, or vertex limits, hazard cells nearest
       the origin-destination corridor line are prioritized until within limits.
    6. If even nearest hazard cells cannot fit within limits, marks is_exceeding_limits
       and emits no_hazard_free_route warning.
    """
    warnings: List[RouteWarningEnum] = []

    # 1. Resolve origin and destination H3 res-8 cells
    origin_cell = latlng_to_cell(origin_lat, origin_lng, res=8)
    dest_cell = latlng_to_cell(dest_lat, dest_lng, res=8)
    origin_exclusion_disk = grid_disk(origin_cell, k=1)

    corridor_line = LineString([(origin_lng, origin_lat), (dest_lng, dest_lat)])
    corridor_buffer = corridor_line.buffer(pad_deg)

    candidate_cells: List[str] = []
    has_unverified_nearby = False
    total_hazards = 0

    for cell, assessment in assessments_by_cell.items():
        if hasattr(assessment, "status"):
            st_val = assessment.status
            status = st_val.value if hasattr(st_val, "value") else str(st_val)
        elif isinstance(assessment, dict):
            status = str(assessment.get("status", "clear"))
        else:
            status = "clear"

        if status in ("official_hazard", "likely_hazard"):
            total_hazards += 1
            # Check exclusions
            if cell == origin_cell or cell in origin_exclusion_disk:
                continue
            if cell == dest_cell:
                continue
            candidate_cells.append(cell)

        elif status == "unverified":
            c_lat, c_lng = cell_to_latlng(cell)
            if corridor_buffer.contains(Point(c_lng, c_lat)):
                has_unverified_nearby = True

    if has_unverified_nearby:
        warnings.append(RouteWarningEnum.UNVERIFIED_REPORTS_NEARBY)

    if not candidate_cells:
        return AvoidSetResult(
            avoid_cells=[],
            avoid_polygon_geojson=None,
            shapely_union=None,
            warnings=warnings,
            total_hazard_cells=total_hazards,
            area_km2=0.0,
            extent_km=0.0,
            pruned=False,
            is_exceeding_limits=False,
        )

    # 2. Build individual Shapely polygons
    cell_polygons: List[Tuple[str, Polygon, float]] = []
    for cell in candidate_cells:
        ring = cell_to_geojson_boundary(cell)
        poly = Polygon(ring)
        c_lat, c_lng = cell_to_latlng(cell)
        # Distance from cell center to corridor LineString
        dist_to_corridor = Point(c_lng, c_lat).distance(corridor_line)
        cell_polygons.append((cell, poly, dist_to_corridor))

    # 3. Check full union
    full_union = unary_union([p for _, p, _ in cell_polygons])
    full_area = _calculate_geom_area_km2(full_union)
    full_extent = _calculate_geom_extent_km(full_union)
    full_vertices = _count_vertices(full_union)

    if full_area <= max_area_km2 and full_extent <= max_extent_km and full_vertices <= max_vertices:
        # Fits comfortably within provider limits
        geojson_geom = mapping(full_union)
        return AvoidSetResult(
            avoid_cells=candidate_cells,
            avoid_polygon_geojson=geojson_geom,
            shapely_union=full_union,
            warnings=warnings,
            total_hazard_cells=total_hazards,
            area_km2=full_area,
            extent_km=full_extent,
            pruned=False,
            is_exceeding_limits=False,
        )

    # 4. Limits exceeded -> Corridor-based pruning (Amendment 1)
    # Sort candidates by distance to corridor ascending (nearest first)
    cell_polygons.sort(key=lambda item: item[2])

    selected_cells: List[str] = []
    selected_polys: List[Polygon] = []
    current_union: Any = None
    last_valid_union: Any = None

    for cell, poly, _ in cell_polygons:
        trial_polys = selected_polys + [poly]
        trial_union = unary_union(trial_polys)
        area_km2 = _calculate_geom_area_km2(trial_union)
        extent_km = _calculate_geom_extent_km(trial_union)
        vertices = _count_vertices(trial_union)

        if area_km2 <= max_area_km2 and extent_km <= max_extent_km and vertices <= max_vertices:
            selected_cells.append(cell)
            selected_polys.append(poly)
            last_valid_union = trial_union
        else:
            # Reached capacity for provider limits
            continue

    if not selected_cells or last_valid_union is None:
        # Cannot fit even a single hazard cell within limits
        warnings.append(RouteWarningEnum.NO_HAZARD_FREE_ROUTE)
        return AvoidSetResult(
            avoid_cells=[],
            avoid_polygon_geojson=None,
            shapely_union=None,
            warnings=warnings,
            total_hazard_cells=total_hazards,
            area_km2=full_area,
            extent_km=full_extent,
            pruned=True,
            is_exceeding_limits=True,
        )

    final_area = _calculate_geom_area_km2(last_valid_union)
    final_extent = _calculate_geom_extent_km(last_valid_union)

    return AvoidSetResult(
        avoid_cells=selected_cells,
        avoid_polygon_geojson=mapping(last_valid_union),
        shapely_union=last_valid_union,
        warnings=warnings,
        total_hazard_cells=total_hazards,
        area_km2=final_area,
        extent_km=final_extent,
        pruned=True,
        is_exceeding_limits=False,
    )


def build_direct_line_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    warnings: Optional[List[RouteWarningEnum]] = None,
    distance_override_m: Optional[float] = None,
) -> RouteResult:
    """Build a transparent fallback direct line route with honest warnings."""
    dist_m = distance_override_m if distance_override_m is not None else haversine_distance_m(origin_lat, origin_lng, dest_lat, dest_lng)
    # Walking speed assumption: 1.2 m/s (~4.3 km/h)
    duration_s = round(dist_m / 1.2, 1)

    route_warnings = list(warnings or [])

    return RouteResult(
        geometry={
            "type": "LineString",
            "coordinates": [
                [round(origin_lng, 6), round(origin_lat, 6)],
                [round(dest_lng, 6), round(dest_lat, 6)],
            ],
        },
        distance_m=dist_m,
        duration_s=duration_s,
        steps=[
            StructuredStep(
                maneuver=ManeuverEnum.CONTINUE,
                street_name=None,
                distance_m=dist_m,
            )
        ],
        provider="direct_line",
        kind=RouteKindEnum.DIRECT_LINE,
        warnings=route_warnings,
        hazard_cells_avoided=0,
    )
