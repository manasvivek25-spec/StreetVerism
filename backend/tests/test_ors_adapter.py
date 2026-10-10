"""Unit and integration tests for OpenRouteService adapter and quota manager (Unit 2)."""

from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest
from shapely.geometry import box

from backend.app.routing.ors_adapter import OpenRouteServiceAdapter
from backend.app.routing.quota import RoutingQuotaManager
from backend.app.routing.types import (
    DEFAULT_ORS_ATTRIBUTION,
    AvoidSetResult,
    ManeuverEnum,
    RouteKindEnum,
    RouteWarningEnum,
)


def test_quota_manager_minute_rate_limit_and_refill():
    """Verify token bucket rate limiter exhausts tokens and blocks excess requests."""
    qm = RoutingQuotaManager(rate_per_min=5, daily_budget=100)
    # 5 tokens available initially
    for _ in range(5):
        assert qm.acquire() is True

    # 6th should fail
    assert qm.acquire() is False


def test_quota_manager_daily_budget():
    """Verify daily budget stops granting tokens when daily limit is reached."""
    qm = RoutingQuotaManager(rate_per_min=100, daily_budget=3)
    assert qm.acquire() is True
    assert qm.acquire() is True
    assert qm.acquire() is True
    assert qm.acquire() is False
    assert qm.get_remaining_daily() == 0


@pytest.mark.anyio
async def test_ors_adapter_unavailable_when_no_api_key():
    """Verify adapter returns None without making any HTTP request when API key is missing."""
    adapter = OpenRouteServiceAdapter(api_key="")
    assert adapter.is_available is False

    result = await adapter.get_directions(13.0, 80.2, 13.05, 80.25)
    assert result is None


@pytest.mark.anyio
async def test_ors_adapter_successful_route_parsing():
    """Verify ORS GeoJSON 200 response parses maneuvers, geometry, attribution, and properties."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [80.2180, 12.9815],
                        [80.2175, 12.9820],
                        [80.2170, 12.9825],
                    ],
                },
                "properties": {
                    "summary": {
                        "distance": 850.0,
                        "duration": 612.0,
                    },
                    "segments": [
                        {
                            "steps": [
                                {"type": 11, "name": "Velachery Bypass Rd", "distance": 250.0},
                                {"type": 0, "name": "100 Feet Rd", "distance": 600.0},
                                {"type": 10, "name": None, "distance": 0.0},
                            ]
                        }
                    ],
                },
            }
        ],
    }
    mock_client.post.return_value = mock_resp

    adapter = OpenRouteServiceAdapter(
        api_key="test-mock-api-key",
        client=mock_client,
    )

    result = await adapter.get_directions(12.9815, 80.2180, 12.9825, 80.2170)

    assert result is not None
    assert result.kind == RouteKindEnum.ROAD_ROUTE
    assert result.distance_m == 850.0
    assert result.duration_s == 612.0
    assert result.provider == "openrouteservice"
    assert result.attribution == DEFAULT_ORS_ATTRIBUTION
    assert len(result.steps) == 3
    assert result.steps[0].maneuver == ManeuverEnum.DEPART
    assert result.steps[0].street_name == "Velachery Bypass Rd"
    assert result.steps[1].maneuver == ManeuverEnum.TURN_LEFT
    assert result.steps[1].street_name == "100 Feet Rd"
    assert result.steps[2].maneuver == ManeuverEnum.ARRIVE


@pytest.mark.anyio
async def test_ors_adapter_post_validation_intersection_warning():
    """Verify route intersecting hazard avoid union triggers NO_HAZARD_FREE_ROUTE warning."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "features": [
            {
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[80.21, 13.01], [80.22, 13.02]],
                },
                "properties": {
                    "summary": {"distance": 500.0, "duration": 300.0},
                    "segments": [],
                },
            }
        ]
    }
    mock_client.post.return_value = mock_resp

    adapter = OpenRouteServiceAdapter(api_key="test-key", client=mock_client)

    # Avoid union box overlapping with the line [80.21, 13.01] to [80.22, 13.02]
    overlap_box = box(80.212, 13.012, 80.218, 13.018)
    avoid_set = AvoidSetResult(
        avoid_cells=["cell1"],
        shapely_union=overlap_box,
    )

    result = await adapter.get_directions(13.01, 80.21, 13.02, 80.22, avoid_set=avoid_set)

    assert result is not None
    assert RouteWarningEnum.NO_HAZARD_FREE_ROUTE in result.warnings
    assert result.hazard_cells_avoided == 0


@pytest.mark.anyio
async def test_ors_adapter_http_error_fallback_tolerance():
    """Verify HTTP 429 rate limit or 500 error cleanly returns None without crashing."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_client.post.return_value = mock_resp_429

    adapter = OpenRouteServiceAdapter(api_key="test-key", client=mock_client)
    res_429 = await adapter.get_directions(13.0, 80.2, 13.01, 80.21)
    assert res_429 is None

    # Exception tolerance
    mock_client.post.side_effect = httpx.ConnectTimeout("Connection timed out")
    res_exc = await adapter.get_directions(13.0, 80.2, 13.01, 80.21)
    assert res_exc is None
