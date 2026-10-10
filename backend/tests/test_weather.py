"""Unit and integration tests for Open-Meteo precipitation ingest (A4 minimal)."""

from unittest.mock import MagicMock
import httpx
import pytest

from backend.app.geo import latlng_to_cell
from backend.app.ingest.open_meteo import OpenMeteoRainProvider
from backend.app.trust.types import CellFeatures


def test_open_meteo_success_parsing_and_aggregation():
    """Verify Open-Meteo 200 response parses hourly precipitation correctly into rain_mm_3h and 24h."""
    mock_client = MagicMock(spec=httpx.Client)

    # 24 hours of mock precipitation (0.5mm each, last 3 hours 2.0mm each)
    mock_precip = [0.5] * 21 + [2.0, 2.0, 2.0]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "latitude": 13.0,
        "longitude": 80.2,
        "hourly": {
            "time": [f"2026-10-10T{i:02d}:00" for i in range(24)],
            "precipitation": mock_precip,
        },
    }
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoRainProvider(client=mock_client)
    test_cell = latlng_to_cell(13.015, 80.225, 8)

    features = provider.get_features_for_cell(test_cell)

    assert features.rain_available is True
    # 21 * 0.5 + 3 * 2.0 = 10.5 + 6.0 = 16.5
    assert features.rain_mm_24h == 16.5
    # last 3 hours: 3 * 2.0 = 6.0
    assert features.rain_mm_3h == 6.0
    assert features.flood_prone is False

    # Check that in-memory cache hit avoids second network call
    mock_client.get.reset_mock()
    features_cached = provider.get_features_for_cell(test_cell)
    assert features_cached.rain_available is True
    assert features_cached.rain_mm_24h == 16.5
    mock_client.get.assert_not_called()


def test_open_meteo_failure_tolerance_429():
    """Verify Open-Meteo 429 rate limit is failure-tolerant and sets rain_available=False."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.json.return_value = {"error": True, "reason": "Rate limit exceeded"}
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoRainProvider(client=mock_client)
    test_cell = latlng_to_cell(12.9815, 80.2180, 8)

    features = provider.get_features_for_cell(test_cell)

    assert features.rain_available is False
    assert features.rain_mm_3h == 0.0
    assert features.rain_mm_24h == 0.0


def test_open_meteo_network_timeout_failure_tolerance():
    """Verify network exception is caught without crashing and returns safe fallback."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.side_effect = httpx.ConnectTimeout("Connection timed out")

    provider = OpenMeteoRainProvider(client=mock_client)
    test_cell = latlng_to_cell(13.08, 80.27, 8)

    features = provider.get_features_for_cell(test_cell)

    assert features.rain_available is False
    assert features.rain_mm_3h == 0.0
    assert features.rain_mm_24h == 0.0


def test_open_meteo_coarse_grid_quantization():
    """Verify nearby cells in the same 0.1 degree grid share the same cached values."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "hourly": {
            "precipitation": [1.0] * 24,
        }
    }
    mock_client.get.return_value = mock_resp

    provider = OpenMeteoRainProvider(client=mock_client)
    cell_a = latlng_to_cell(13.01, 80.21, 8)
    cell_b = latlng_to_cell(13.04, 80.24, 8)

    f_a = provider.get_features_for_cell(cell_a)
    assert f_a.rain_available is True
    assert mock_client.get.call_count == 1

    # cell_b has round(13.04, 1) == 13.0 and round(80.24, 1) == 80.2, so it should hit the same cache!
    f_b = provider.get_features_for_cell(cell_b)
    assert f_b.rain_available is True
    assert mock_client.get.call_count == 1
