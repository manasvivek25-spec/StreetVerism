"""Generators for native map deep links (Google Maps, Apple Maps, and Geo URI)."""

from typing import Dict
from backend.app.routing.types import MapsUrls


def generate_maps_urls(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    mode: str = "walk",
) -> MapsUrls:
    """Generate universal native maps links from verified URL schemes.
    
    Verified Schemes:
    - Google Maps Universal URL:
      https://www.google.com/maps/dir/?api=1&origin={lat},{lng}&destination={lat},{lng}&travelmode={walking|driving}
    - Apple Maps URL Scheme:
      https://maps.apple.com/?saddr={lat},{lng}&daddr={lat},{lng}&dirflg={w|d}
    - RFC 5870 Geo URI:
      geo:{lat},{lng}?q={lat},{lng}
    """
    travel_mode_google = "driving" if mode == "drive" else "walking"
    dirflg_apple = "d" if mode == "drive" else "w"

    google_url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={origin_lat:.4f},{origin_lng:.4f}"
        f"&destination={dest_lat:.4f},{dest_lng:.4f}"
        f"&travelmode={travel_mode_google}"
    )

    apple_url = (
        f"https://maps.apple.com/"
        f"?saddr={origin_lat:.4f},{origin_lng:.4f}"
        f"&daddr={dest_lat:.4f},{dest_lng:.4f}"
        f"&dirflg={dirflg_apple}"
    )

    geo_uri = f"geo:{dest_lat:.4f},{dest_lng:.4f}?q={dest_lat:.4f},{dest_lng:.4f}"

    return MapsUrls(google=google_url, apple=apple_url, geo=geo_uri)
