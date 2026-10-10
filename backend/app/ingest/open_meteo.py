"""Open-Meteo precipitation ingest provider (A4 minimal).

Fetches hourly precipitation from the Open-Meteo Forecast API:
- Endpoint: https://api.open-meteo.com/v1/forecast
- Parameters: latitude, longitude, hourly=precipitation, past_hours=24, forecast_days=1
- Coarse areas: quantizes H3 cells to 0.1 degree grid (~11km) to minimize calls.
- In-memory cache: 15-minute TTL per coarse coordinate.
- Failure-tolerant: handles HTTP 429/500, network timeouts, and offline environments
  gracefully by returning rain_available=False, never crashing or failing callers.
"""

import logging
import os
import time
from typing import Dict, Optional, Tuple

import httpx

from backend.app.geo import cell_to_latlng
from backend.app.trust.types import CellFeatures

logger = logging.getLogger(__name__)

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CACHE_TTL_S = 900.0  # 15 minutes


class OpenMeteoRainProvider:
    """Coarse-area cached, failure-tolerant Open-Meteo precipitation ingest provider."""

    def __init__(
        self,
        base_url: str = OPEN_METEO_BASE_URL,
        cache_ttl_s: float = WEATHER_CACHE_TTL_S,
        failure_ttl_s: float = 300.0,
        timeout_s: float = 2.0,
        client: Optional[httpx.Client] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        self.base_url = base_url
        self.cache_ttl_s = cache_ttl_s
        self.failure_ttl_s = failure_ttl_s
        self.timeout_s = timeout_s
        self._custom_client = client
        if enabled is None:
            if client is not None:
                self.enabled = True
            else:
                self.enabled = os.getenv("WEATHER_ENABLED", "0").lower() in ("1", "true", "yes")
        else:
            self.enabled = enabled
        # In-memory cache: (coarse_lat, coarse_lng) -> (rain_3h, rain_24h, expires_at)
        self._cache: Dict[Tuple[float, float], Tuple[float, float, float]] = {}

    def clear_cache(self) -> None:
        """Clear all cached precipitation data."""
        self._cache.clear()

    def get_features_for_cell(self, cell: str) -> CellFeatures:
        """Compute CellFeatures for given H3 cell from Open-Meteo or cache."""
        if not self.enabled:
            return CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False, rain_available=False)

        try:
            lat, lng = cell_to_latlng(cell)
        except Exception:
            return CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False, rain_available=False)

        coarse_key = (round(lat, 1), round(lng, 1))
        now_ts = time.time()

        # 1. Check in-memory cache
        if coarse_key in self._cache:
            rain_3h, rain_24h, expires_at = self._cache[coarse_key]
            if now_ts < expires_at:
                return CellFeatures(
                    rain_mm_3h=rain_3h,
                    rain_mm_24h=rain_24h,
                    flood_prone=False,
                    rain_available=(rain_24h > 0.0 or rain_3h > 0.0 or expires_at - now_ts > self.failure_ttl_s),
                )

        # 2. Fetch fresh weather from Open-Meteo
        params = {
            "latitude": coarse_key[0],
            "longitude": coarse_key[1],
            "hourly": "precipitation",
            "past_hours": 24,
            "forecast_days": 1,
        }

        try:
            if self._custom_client:
                resp = self._custom_client.get(self.base_url, params=params, timeout=self.timeout_s)
            else:
                with httpx.Client(timeout=self.timeout_s) as client:
                    resp = client.get(self.base_url, params=params)

            if resp.status_code == 200:
                data = resp.json()
                hourly = data.get("hourly", {})
                precipitation = hourly.get("precipitation", [])

                if precipitation:
                    # past_hours=24: the past 24 hourly values precede future hours
                    past_vals = [float(v) for v in precipitation[:24] if v is not None]
                    rain_24h = max(0.0, sum(past_vals))
                    past_3_vals = past_vals[-3:] if len(past_vals) >= 3 else past_vals
                    rain_3h = max(0.0, sum(past_3_vals))
                    rain_24h = max(rain_3h, rain_24h)

                    rain_3h = round(rain_3h, 2)
                    rain_24h = round(rain_24h, 2)

                    # Store positive hit in cache
                    self._cache[coarse_key] = (rain_3h, rain_24h, now_ts + self.cache_ttl_s)

                    return CellFeatures(
                        rain_mm_3h=rain_3h,
                        rain_mm_24h=rain_24h,
                        flood_prone=False,
                        rain_available=True,
                    )
                else:
                    logger.debug("Open-Meteo response missing precipitation data for %s", coarse_key)
            elif resp.status_code == 429:
                logger.warning("Open-Meteo rate limit reached (HTTP 429). Weather features unavailable.")
            else:
                logger.warning("Open-Meteo HTTP %d for %s", resp.status_code, coarse_key)
        except Exception as exc:
            logger.debug("Open-Meteo query failed for %s: %s", coarse_key, exc)

        # Negative caching on failure: cache (0.0, 0.0) for failure_ttl_s to prevent repeated slow requests
        self._cache[coarse_key] = (0.0, 0.0, now_ts + self.failure_ttl_s)

        return CellFeatures(
            rain_mm_3h=0.0,
            rain_mm_24h=0.0,
            flood_prone=False,
            rain_available=False,
        )

    def __call__(self, cell: str) -> CellFeatures:
        """Callable interface matching DataContext.features_provider."""
        return self.get_features_for_cell(cell)

