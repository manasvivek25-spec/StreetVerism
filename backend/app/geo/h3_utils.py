"""Centralized H3 geospatial utilities for StreetVerism.

ALL calls to the h3 library must remain within this module.
H3 version: 4.x
Conventions:
- Coordinates in JSON/Python: (lat, lng)
- Coordinates in GeoJSON: [lng, lat]
"""

from typing import Any, List, Set, Tuple
import h3


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


def geojson_polygon_to_cells(geojson_poly: dict[str, Any], res: int = 8) -> Set[str]:
    """Convert a GeoJSON Polygon mapping to a set of intersecting H3 cells."""
    h3_shape = h3.geo_to_h3shape(geojson_poly)
    cells = h3.polygon_to_cells(h3_shape, res)
    return set(cells)


def cells_in_bbox(min_lng: float, min_lat: float, max_lng: float, max_lat: float, res: int = 8) -> Set[str]:
    """Compute H3 cells intersecting a bounding box [minLng, minLat, maxLng, maxLat]."""
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
    return geojson_polygon_to_cells(bbox_poly, res)
