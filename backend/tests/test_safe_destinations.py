"""Unit tests for Unit 1: Safe destination ranking and avoid set geometry."""

import pytest
from shapely.geometry import shape

from backend.app.geo.h3_utils import (
    cell_to_latlng,
    grid_disk,
    haversine_distance_m,
    latlng_to_cell,
)
from backend.app.routing.avoid import (
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
    ManeuverEnum,
    RouteKindEnum,
    RouteWarningEnum,
)
from backend.app.trust.types import CellAssessment, CellStatus


class DummyAssessment:
    """Mock assessment object for testing."""
    def __init__(self, status: str):
        self.status = status


def test_calculate_initial_bearing():
    """Verify forward azimuth calculation across cardinal and intercardinal bearings."""
    # Due North: (13.0, 80.0) to (14.0, 80.0) -> ~0°
    assert calculate_initial_bearing(13.0, 80.0, 14.0, 80.0) == 0.0

    # Due East: (13.0, 80.0) to (13.0, 81.0) -> ~90°
    b_east = calculate_initial_bearing(13.0, 80.0, 13.0, 81.0)
    assert 89.0 <= b_east <= 91.0

    # Due South: (14.0, 80.0) to (13.0, 80.0) -> ~180°
    assert calculate_initial_bearing(14.0, 80.0, 13.0, 80.0) == 180.0

    # Due West: (13.0, 81.0) to (13.0, 80.0) -> ~270°
    b_west = calculate_initial_bearing(13.0, 81.0, 13.0, 80.0)
    assert 269.0 <= b_west <= 271.0

    # Identical points -> 0.0
    assert calculate_initial_bearing(13.0, 80.0, 13.0, 80.0) == 0.0


def test_bearing_to_compass_sectors():
    """Verify 8-point compass sector mappings."""
    assert bearing_to_compass(0.0) == "N"
    assert bearing_to_compass(359.0) == "N"
    assert bearing_to_compass(15.0) == "N"
    assert bearing_to_compass(45.0) == "NE"
    assert bearing_to_compass(90.0) == "E"
    assert bearing_to_compass(135.0) == "SE"
    assert bearing_to_compass(180.0) == "S"
    assert bearing_to_compass(225.0) == "SW"
    assert bearing_to_compass(270.0) == "W"
    assert bearing_to_compass(315.0) == "NW"


def test_is_shelter_safe():
    """Evaluate shelter safety classification under various assessment states."""
    lat, lng = 13.015, 80.225
    cell = latlng_to_cell(lat, lng, 8)

    # Missing assessment -> safe clear
    safe, c, status = is_shelter_safe(lat, lng, {})
    assert safe is True
    assert c == cell
    assert status == "clear"

    # Official hazard -> unsafe
    safe, _, status = is_shelter_safe(lat, lng, {cell: DummyAssessment("official_hazard")})
    assert safe is False
    assert status == "official_hazard"

    # Likely hazard -> unsafe
    safe, _, status = is_shelter_safe(lat, lng, {cell: DummyAssessment("likely_hazard")})
    assert safe is False
    assert status == "likely_hazard"

    # Unverified -> safe
    safe, _, status = is_shelter_safe(lat, lng, {cell: DummyAssessment("unverified")})
    assert safe is True
    assert status == "unverified"


def test_select_safe_destinations_ranking_and_filtering():
    """Verify shelters are filtered for safety and sorted by proximity ascending."""
    origin_lat, origin_lng = 13.000, 80.200

    # 3 demo shelters
    sh_near = {"id": "sh_1", "name": "Near Safe Center", "lat": 13.010, "lng": 80.210}
    sh_far = {"id": "sh_2", "name": "Far Safe Center", "lat": 13.050, "lng": 80.250}
    sh_haz = {"id": "sh_3", "name": "Hazardous Center", "lat": 13.005, "lng": 80.205}

    haz_cell = latlng_to_cell(sh_haz["lat"], sh_haz["lng"], 8)
    assessments = {
        haz_cell: DummyAssessment("official_hazard"),
    }

    results = select_safe_destinations(
        origin_lat, origin_lng, [sh_far, sh_haz, sh_near], assessments, limit=2
    )

    # sh_haz must be filtered out
    assert len(results) == 2
    assert results[0].id == "sh_1"
    assert results[1].id == "sh_2"
    assert results[0].distance_m < results[1].distance_m
    assert results[0].compass_direction == "NE"
    assert results[0].status == "clear"


def test_select_safe_destinations_empty_when_all_hazardous():
    """Verify returns empty list when all available shelters are submerged/hazardous."""
    origin_lat, origin_lng = 13.000, 80.200
    sh1 = {"id": "sh_1", "name": "Center 1", "lat": 13.010, "lng": 80.210}
    c1 = latlng_to_cell(sh1["lat"], sh1["lng"], 8)

    assessments = {c1: DummyAssessment("likely_hazard")}
    results = select_safe_destinations(origin_lat, origin_lng, [sh1], assessments)
    assert results == []


def test_build_avoid_set_origin_and_dest_exclusion():
    """Verify origin cell, origin k=1 disk, and destination cell are never in avoid set."""
    origin_lat, origin_lng = 13.015, 80.225
    dest_lat, dest_lng = 13.060, 80.240

    orig_cell = latlng_to_cell(origin_lat, origin_lng, 8)
    dest_cell = latlng_to_cell(dest_lat, dest_lng, 8)
    orig_k1 = grid_disk(orig_cell, k=1)

    # Mark origin, all k=1 neighbors, destination, and a separate intermediate cell as official_hazard
    intermediate_lat, intermediate_lng = 13.035, 80.230
    inter_cell = latlng_to_cell(intermediate_lat, intermediate_lng, 8)
    assert inter_cell not in orig_k1
    assert inter_cell != dest_cell

    assessments = {
        orig_cell: DummyAssessment("official_hazard"),
        dest_cell: DummyAssessment("official_hazard"),
        inter_cell: DummyAssessment("official_hazard"),
    }
    for c in orig_k1:
        assessments[c] = DummyAssessment("official_hazard")

    avoid_result = build_avoid_set(origin_lat, origin_lng, dest_lat, dest_lng, assessments)

    # Origin cell and entire k=1 ring must be excluded
    assert orig_cell not in avoid_result.avoid_cells
    for c in orig_k1:
        assert c not in avoid_result.avoid_cells
    # Destination must be excluded
    assert dest_cell not in avoid_result.avoid_cells

    # Only intermediate cell should remain
    assert inter_cell in avoid_result.avoid_cells
    assert avoid_result.avoid_polygon_geojson is not None
    assert avoid_result.avoid_polygon_geojson["type"] in ("Polygon", "MultiPolygon")


def test_build_avoid_set_unverified_warning_never_avoided():
    """Verify unverified cells are NOT in avoid set, but trigger warning if near corridor."""
    origin_lat, origin_lng = 13.015, 80.225
    dest_lat, dest_lng = 13.050, 80.230

    mid_lat, mid_lng = 13.030, 80.227
    unverified_cell = latlng_to_cell(mid_lat, mid_lng, 8)

    assessments = {
        unverified_cell: DummyAssessment("unverified"),
    }

    avoid_result = build_avoid_set(origin_lat, origin_lng, dest_lat, dest_lng, assessments)
    assert unverified_cell not in avoid_result.avoid_cells
    assert avoid_result.avoid_cells == []
    assert RouteWarningEnum.UNVERIFIED_REPORTS_NEARBY in avoid_result.warnings


def test_build_avoid_set_corridor_pruning_with_fake_limits():
    """Verify that hazard cells are pruned by corridor distance when limits are exceeded."""
    origin_lat, origin_lng = 13.000, 80.200
    dest_lat, dest_lng = 13.040, 80.200

    # Create 3 hazard cells:
    # cell_close: directly on the corridor line
    # cell_mid: 0.01 deg away
    # cell_far: 0.05 deg away
    c_close = latlng_to_cell(13.020, 80.200, 8)
    c_mid = latlng_to_cell(13.020, 80.210, 8)
    c_far = latlng_to_cell(13.020, 80.250, 8)

    assessments = {
        c_close: DummyAssessment("official_hazard"),
        c_mid: DummyAssessment("official_hazard"),
        c_far: DummyAssessment("official_hazard"),
    }

    # Set fake tight area limit allowing only ~1 cell (~0.7 km²)
    fake_max_area = 1.0  # 1.0 km²

    res = build_avoid_set(
        origin_lat, origin_lng, dest_lat, dest_lng, assessments, max_area_km2=fake_max_area
    )

    assert res.pruned is True
    assert res.is_exceeding_limits is False
    assert res.area_km2 <= fake_max_area
    # Closest cell to corridor must be preserved first
    assert c_close in res.avoid_cells
    assert c_far not in res.avoid_cells


def test_build_avoid_set_impossible_limits_fallback():
    """Verify that if even a single cell exceeds limits, no_hazard_free_route is emitted."""
    origin_lat, origin_lng = 13.000, 80.200
    dest_lat, dest_lng = 13.040, 80.200

    c_haz = latlng_to_cell(13.020, 80.200, 8)
    assessments = {c_haz: DummyAssessment("official_hazard")}

    # Extreme fake limit: 0.00001 km²
    res = build_avoid_set(
        origin_lat, origin_lng, dest_lat, dest_lng, assessments, max_area_km2=0.00001
    )

    assert res.pruned is True
    assert res.is_exceeding_limits is True
    assert RouteWarningEnum.NO_HAZARD_FREE_ROUTE in res.warnings
    assert res.avoid_cells == []
    assert res.avoid_polygon_geojson is None


def test_build_direct_line_route():
    """Verify direct line route construction and GeoJSON coordinates."""
    orig_lat, orig_lng = 13.015, 80.225
    dest_lat, dest_lng = 13.050, 80.250

    res = build_direct_line_route(
        orig_lat, orig_lng, dest_lat, dest_lng, warnings=[RouteWarningEnum.NO_HAZARD_FREE_ROUTE]
    )

    assert res.kind == RouteKindEnum.DIRECT_LINE
    assert res.provider == "direct_line"
    assert res.geometry["type"] == "LineString"
    assert res.geometry["coordinates"] == [
        [round(orig_lng, 6), round(orig_lat, 6)],
        [round(dest_lng, 6), round(dest_lat, 6)],
    ]
    assert res.distance_m > 0.0
    assert res.duration_s > 0.0
    assert len(res.steps) == 1
    assert res.steps[0].maneuver == ManeuverEnum.CONTINUE
    assert RouteWarningEnum.NO_HAZARD_FREE_ROUTE in res.warnings
    assert res.hazard_cells_avoided == 0
