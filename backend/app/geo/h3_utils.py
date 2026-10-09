"""Centralized H3 geospatial utilities for StreetVerism.

ALL calls to the h3 library must remain within this module.
H3 version: 4.5.0
Conventions:
- Coordinates in JSON/Python: (lat, lng)
- Coordinates in GeoJSON: [lng, lat]
"""

import math
from typing import Any, List, Set, Tuple
import h3

# Maximum allowable bounding box span in degrees (~160 km) to prevent resource exhaustion
MAX_BBOX_DELTA_DEG = 1.5


def latlng_to_cell(lat: float, lng: float, res: int = 8) -> str:
    """Convert (latitude, longitude) to H3 cell index at the specified resolution."""
    return h3.latlng_to_cell(lat, lng, res)


def cell_to_latlng(cell: str) -> Tuple[float, float]:
    """Convert H3 cell index to center (latitude, longitude)."""
    return h3.cell_to_latlng(cell)


def cell_to_parent(cell: str, res: int = 7) -> str:
    """Get parent H3 cell index at resolution (default 7)."""
    return h3.cell_to_parent(cell, res)


def cell_to_geojson_boundary(cell: str) -> List[List[float]]:
    """Convert H3 cell to GeoJSON polygon boundary ring: list of [lng, lat] coordinates.
    
    h3.cell_to_boundary returns a tuple of (lat, lng) pairs.
    GeoJSON coordinates MUST be [lng, lat] and closed (first == last).
    """
    latlng_boundary = h3.cell_to_boundary(cell)
    # Convert each (lat, lng) to [lng, lat]
    geojson_ring = [[round(lng, 6), round(lat, 6)] for lat, lng in latlng_boundary]
    # Ensure linear ring is closed
    if geojson_ring and geojson_ring[0] != geojson_ring[-1]:
        geojson_ring.append(geojson_ring[0])
    return geojson_ring


def cell_to_geojson_polygon(cell: str) -> List[List[List[float]]]:
    """Return standard GeoJSON Polygon coordinates structure: [[[lng, lat], ...]]."""
    return [cell_to_geojson_boundary(cell)]


def cell_to_polygon_lnglat(cell: str) -> List[List[List[float]]]:
    """Alias for cell_to_geojson_polygon returning GeoJSON-order [[[lng, lat], ...]]."""
    return cell_to_geojson_polygon(cell)


def geojson_polygon_to_cells(geojson_poly: dict[str, Any], res: int = 8) -> Set[str]:
    """Convert a GeoJSON Polygon mapping to a set of intersecting H3 cells."""
    h3_shape = h3.geo_to_h3shape(geojson_poly)
    cells = h3.polygon_to_cells(h3_shape, res)
    return set(cells)


def cells_in_bbox(min_lng: float, min_lat: float, max_lng: float, max_lat: float, res: int = 8) -> Set[str]:
    """Compute H3 cells covering a bounding box [minLng, minLat, maxLng, maxLat].
    
    Enforces maximum bounding box size.
    Uses geo_to_h3shape with GeoJSON [lng, lat] ordering.
    Includes corner and center cell fallbacks so tiny bounding boxes never return empty.
    """
    delta_lng = max_lng - min_lng
    delta_lat = max_lat - min_lat

    if delta_lng < 0 or delta_lat < 0:
        raise ValueError("Invalid bounding box: min coordinates exceed max coordinates.")

    if delta_lng > MAX_BBOX_DELTA_DEG or delta_lat > MAX_BBOX_DELTA_DEG:
        raise ValueError(
            f"Bounding box span ({delta_lng:.2f}x{delta_lat:.2f} deg) exceeds maximum allowable limit of {MAX_BBOX_DELTA_DEG} degrees."
        )

    # GeoJSON coordinates strictly use [lng, lat]
    bbox_poly = {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lng, min_lat],
                [max_lng, min_lat],
                [max_lng, max_lat],
                [min_lng, max_lat],
                [min_lng, min_lat],
            ]
        ],
    }
    h3_shape = h3.geo_to_h3shape(bbox_poly)
    cells = set(h3.polygon_to_cells(h3_shape, res))

    # Corner and center fallback ensures tiny bboxes always resolve enclosing cell(s)
    center_lat = (min_lat + max_lat) / 2.0
    center_lng = (min_lng + max_lng) / 2.0

    cells.add(latlng_to_cell(min_lat, min_lng, res))
    cells.add(latlng_to_cell(min_lat, max_lng, res))
    cells.add(latlng_to_cell(max_lat, min_lng, res))
    cells.add(latlng_to_cell(max_lat, max_lng, res))
    cells.add(latlng_to_cell(center_lat, center_lng, res))

    return cells


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate Great Circle distance in meters between two (lat, lng) points."""
    r = 6371000.0  # Earth radius in meters
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 1)
