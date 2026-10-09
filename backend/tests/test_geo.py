"""Tests for H3 geospatial helpers, coordinate swap prevention, and bbox edge cases."""

import pytest
import h3

from backend.app.geo import (
    cell_to_latlng,
    cell_to_parent,
    cell_to_polygon_lnglat,
    cells_in_bbox,
    haversine_distance_m,
    latlng_to_cell,
)


def test_h3_version_and_function_signatures():
    """Confirm installed H3 version is 4.x and core function names exist."""
    assert h3.__version__.startswith("4."), f"Expected H3 v4, got {h3.__version__}"
    assert hasattr(h3, "latlng_to_cell")
    assert hasattr(h3, "cell_to_latlng")
    assert hasattr(h3, "cell_to_boundary")
    assert hasattr(h3, "cell_to_parent")
    assert hasattr(h3, "polygon_to_cells")
    assert hasattr(h3, "geo_to_h3shape")


def test_chennai_coordinate_order_swap_prevention():
    """Verify coordinate order: Python functions take (lat, lng), GeoJSON outputs [lng, lat].
    
    Uses known Chennai reference point: Lat 13.04 N, Lng 80.23 E.
    Ensures the classic (lat, lng) vs [lng, lat] coordinate swap bug is caught.
    """
    lat, lng = 13.04, 80.23
    cell = latlng_to_cell(lat, lng, 8)
    assert isinstance(cell, str) and len(cell) == 15

    # Center check
    center_lat, center_lng = cell_to_latlng(cell)
    assert 13.0 <= center_lat <= 13.1, f"Latitude was swapped or corrupted: {center_lat}"
    assert 80.2 <= center_lng <= 80.3, f"Longitude was swapped or corrupted: {center_lng}"

    # Polygon boundary check: GeoJSON strictly requires [lng, lat]
    polygon = cell_to_polygon_lnglat(cell)
    assert isinstance(polygon, list)
    ring = polygon[0]
    assert len(ring) >= 7  # Hexagon has 6 vertices + 1 closing point
    assert ring[0] == ring[-1], "GeoJSON linear ring must be closed"

    for pt in ring:
        pt_lng, pt_lat = pt[0], pt[1]
        assert 80.2 <= pt_lng <= 80.3, f"GeoJSON first coordinate must be longitude (~80.2): got {pt_lng}"
        assert 13.0 <= pt_lat <= 13.1, f"GeoJSON second coordinate must be latitude (~13.0): got {pt_lat}"


def test_parent_cell_res7():
    """Verify parent cell at resolution 7."""
    cell8 = latlng_to_cell(13.04, 80.23, 8)
    cell7 = cell_to_parent(cell8, 7)
    assert h3.get_resolution(cell7) == 7
    assert h3.get_resolution(cell8) == 8


def test_cells_in_bbox_tiny_bbox_fallback():
    """Verify that a tiny bounding box returns the enclosing cell(s) rather than empty set."""
    # 10m x 10m bbox near Chennai center
    min_lng, min_lat = 80.23000, 13.04000
    max_lng, max_lat = 80.23010, 13.04010

    cells = cells_in_bbox(min_lng, min_lat, max_lng, max_lat, 8)
    assert len(cells) > 0, "Tiny bbox must not return empty cell set"
    expected_cell = latlng_to_cell(13.04000, 80.23000, 8)
    assert expected_cell in cells


def test_cells_in_bbox_max_size_enforcement():
    """Verify that bounding boxes exceeding MAX_BBOX_DELTA_DEG raise a ValueError."""
    with pytest.raises(ValueError, match="exceeds maximum allowable limit"):
        cells_in_bbox(80.0, 12.0, 82.5, 14.5, 8)  # 2.5 deg span > 1.5 limit


def test_haversine_distance():
    """Verify great circle distance calculation between known landmarks in Chennai."""
    # Chennai Central Railway Station (13.0827, 80.2707) to Guindy Metro (13.0067, 80.2025)
    # Expected distance is ~11.0 to 11.5 km (11,000 - 11,500 m)
    dist = haversine_distance_m(13.0827, 80.2707, 13.0067, 80.2025)
    assert 11000.0 <= dist <= 12000.0, f"Calculated unexpected distance: {dist}m"
