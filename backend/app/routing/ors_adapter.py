"""OpenRouteService provider adapter (Unit 2).

Integrates with OpenRouteService (HeiGIT) v2 Directions API:
- Endpoint: POST {base_url}/v2/directions/{profile}/geojson
- Profile: foot-walking (default) or driving-car
- Options: avoid_polygons GeoJSON Polygon or MultiPolygon
- Authentication: Authorization header with ROUTING_API_KEY from environment
- Attribution: "© openrouteservice by HeiGIT | Map data © OpenStreetMap contributors"
- Quota: Enforced via RoutingQuotaManager (token bucket + daily budget)
- Post-validation: Shapely verification that route does not intersect hazard union.
- Failure tolerance: Clean fallback to direct line on errors, timeouts, or rate limits.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx
from shapely.geometry import LineString, shape

from backend.app.routing.quota import RoutingQuotaManager
from backend.app.routing.types import (
    DEFAULT_ORS_ATTRIBUTION,
    AvoidSetResult,
    ManeuverEnum,
    RouteKindEnum,
    RouteResult,
    RouteWarningEnum,
    StructuredStep,
)

logger = logging.getLogger(__name__)

ORS_MANEUVER_MAP: Dict[int, ManeuverEnum] = {
    0: ManeuverEnum.TURN_LEFT,
    1: ManeuverEnum.TURN_RIGHT,
    2: ManeuverEnum.SHARP_LEFT,
    3: ManeuverEnum.SHARP_RIGHT,
    4: ManeuverEnum.SLIGHT_LEFT,
    5: ManeuverEnum.SLIGHT_RIGHT,
    6: ManeuverEnum.CONTINUE,
    7: ManeuverEnum.ROUNDABOUT,
    8: ManeuverEnum.ROUNDABOUT,
    9: ManeuverEnum.UTURN,
    10: ManeuverEnum.ARRIVE,
    11: ManeuverEnum.DEPART,
    12: ManeuverEnum.SLIGHT_LEFT,
    13: ManeuverEnum.SLIGHT_RIGHT,
}


class OpenRouteServiceAdapter:
    """Async adapter for OpenRouteService v2 Directions API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        quota_manager: Optional[RoutingQuotaManager] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("ROUTING_API_KEY", "").strip()
        self.base_url = (base_url or os.getenv("ROUTING_BASE_URL", "https://api.openrouteservice.org")).rstrip("/")
        self.quota = quota_manager or RoutingQuotaManager()
        self._client = client

    @property
    def is_available(self) -> bool:
        """True if an API key is configured."""
        return bool(self.api_key)

    async def get_directions(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        profile: str = "foot-walking",
        avoid_set: Optional[AvoidSetResult] = None,
    ) -> Optional[RouteResult]:
        """Request a road route from OpenRouteService avoiding specified hazard zones."""
        if not self.is_available:
            logger.debug("OpenRouteService adapter unavailable: ROUTING_API_KEY not configured.")
            return None

        # Check quota token bucket and daily limit
        if not self.quota.acquire():
            logger.warning("OpenRouteService quota exceeded (minute rate limit or daily budget reached).")
            return None

        # Format coordinates: [[lng, lat], [lng, lat]]
        coordinates = [
            [round(origin_lng, 5), round(origin_lat, 5)],
            [round(dest_lng, 5), round(dest_lat, 5)],
        ]

        # Map travel profile
        ors_profile = "driving-car" if profile in ("driving-car", "drive") else "foot-walking"
        url = f"{self.base_url}/v2/directions/{ors_profile}/geojson"

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, application/geo+json",
        }

        # Build payload
        payload: Dict[str, Any] = {
            "coordinates": coordinates,
            "instructions": True,
            "elevation": False,
        }

        if avoid_set and avoid_set.avoid_polygon_geojson and not avoid_set.is_exceeding_limits:
            payload["options"] = {
                "avoid_polygons": avoid_set.avoid_polygon_geojson,
            }

        try:
            if self._client:
                resp = await self._client.post(url, json=payload, headers=headers, timeout=4.0)
            else:
                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                return self._parse_ors_response(data, avoid_set)
            elif resp.status_code == 429:
                logger.warning("OpenRouteService API rate limit reached (HTTP 429). Falling back to direct line.")
            elif resp.status_code == 404:
                logger.warning("OpenRouteService: No route found between origin and destination (HTTP 404).")
            else:
                logger.warning("OpenRouteService request failed with HTTP %d.", resp.status_code)
        except Exception as exc:
            logger.warning("OpenRouteService request exception: %s. Falling back to direct line.", exc)

        return None

    def _parse_ors_response(
        self,
        data: Dict[str, Any],
        avoid_set: Optional[AvoidSetResult] = None,
    ) -> Optional[RouteResult]:
        """Parse ORS GeoJSON response into RouteResult and perform post-validation."""
        features = data.get("features", [])
        if not features:
            return None

        feat = features[0]
        geometry = feat.get("geometry", {})
        coords = geometry.get("coordinates", [])
        if not coords:
            return None

        properties = feat.get("properties", {})
        summary = properties.get("summary", {})
        distance_m = float(summary.get("distance", 0.0))
        duration_s = float(summary.get("duration", 0.0))

        # Parse steps
        steps: List[StructuredStep] = []
        segments = properties.get("segments", [])
        for seg in segments:
            for s in seg.get("steps", []):
                maneuver_code = int(s.get("type", 14))
                maneuver_enum = ORS_MANEUVER_MAP.get(maneuver_code, ManeuverEnum.UNKNOWN)
                street_name = s.get("name") or None
                step_dist = float(s.get("distance", 0.0))
                steps.append(
                    StructuredStep(
                        maneuver=maneuver_enum,
                        street_name=street_name,
                        distance_m=round(step_dist, 1),
                    )
                )

        warnings: List[RouteWarningEnum] = []

        # Post-validation: Check Shapely intersection with hazard union
        if avoid_set and avoid_set.shapely_union is not None:
            try:
                route_geom = shape(geometry)
                if route_geom.intersects(avoid_set.shapely_union):
                    # Route clips into hazard area
                    warnings.append(RouteWarningEnum.NO_HAZARD_FREE_ROUTE)
            except Exception as e:
                logger.debug("Post-validation geometry check error: %s", e)

        # Honest count of hazard cells avoided
        hazard_avoided = 0
        if avoid_set and avoid_set.avoid_cells:
            if RouteWarningEnum.NO_HAZARD_FREE_ROUTE not in warnings:
                hazard_avoided = len(avoid_set.avoid_cells)

        return RouteResult(
            geometry=geometry,
            distance_m=round(distance_m, 1),
            duration_s=round(duration_s, 1),
            steps=steps,
            provider="openrouteservice",
            kind=RouteKindEnum.ROAD_ROUTE,
            warnings=warnings,
            hazard_cells_avoided=hazard_avoided,
            attribution=DEFAULT_ORS_ATTRIBUTION,
        )
