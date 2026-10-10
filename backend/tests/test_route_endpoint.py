"""Comprehensive unit and integration tests for GET /api/route (Unit 3a)."""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes import (
    clear_cells_cache,
    init_scenario,
    set_custom_repos,
)
from backend.app.config import get_settings
from backend.app.main import app
from backend.app.repositories import (
    InMemoryAlertRepo,
    InMemoryCheckinRepo,
    InMemoryReportRepo,
    InMemoryShelterRepo,
)
from backend.app.services import (
    load_and_validate_templates,
    seed_shelters_from_file,
)
from backend.app.services.route_service import clear_route_cache, _CLIENT_TIMESTAMPS

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SHELTERS_FILE = ROOT_DIR / "data" / "shelters.json"
TEMPLATES_DIR = ROOT_DIR / "data" / "templates"
SCENARIO_FILE = ROOT_DIR / "data" / "scenarios" / "michaung_replay.json"


@pytest.fixture(autouse=True)
def setup_route_environment(monkeypatch):
    """Isolate repositories, seed shelters, and configure MOCK=0 for route tests."""
    clear_route_cache()
    _CLIENT_TIMESTAMPS.clear()

    alert_repo = InMemoryAlertRepo()
    report_repo = InMemoryReportRepo()
    checkin_repo = InMemoryCheckinRepo()
    shelter_repo = InMemoryShelterRepo()

    set_custom_repos(
        alert_repo=alert_repo,
        report_repo=report_repo,
        checkin_repo=checkin_repo,
        shelter_repo=shelter_repo,
    )

    seed_shelters_from_file(SHELTERS_FILE, shelter_repo)
    load_and_validate_templates(TEMPLATES_DIR)
    init_scenario(SCENARIO_FILE, SHELTERS_FILE)
    clear_cells_cache()

    monkeypatch.setenv("MOCK", "0")
    monkeypatch.setenv("AUTHORITY_KEY", "test-authority-secret-key-123")
    get_settings.cache_clear()

    yield

    clear_route_cache()
    _CLIENT_TIMESTAMPS.clear()
    clear_cells_cache()
    get_settings.cache_clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_route_outside_coverage(client):
    """Verify points outside service bounding box return kind=none with outside_coverage warning."""
    # Mumbai coordinates
    resp = client.get("/api/route?lat=18.9220&lng=72.8347")
    assert resp.status_code == 200
    data = resp.json()

    assert data["kind"] == "none"
    assert data["geometry"] is None
    assert data["destination"] is None
    assert data["alternatives"] == []
    assert data["maps_urls"] is None
    assert data["attribution"] is None
    assert any(w["key"] == "outside_coverage" for w in data["warnings"])


def test_route_invalid_input_validation(client):
    """Verify coordinate and mode input validation (422 Unprocessable Entity)."""
    # Invalid lat > 90
    resp_lat = client.get("/api/route?lat=95.0&lng=80.22")
    assert resp_lat.status_code == 422

    # Invalid lng < -180
    resp_lng = client.get("/api/route?lat=13.0&lng=-185.0")
    assert resp_lng.status_code == 422

    # Invalid travel mode
    resp_mode = client.get("/api/route?lat=13.0&lng=80.22&mode=flying")
    assert resp_mode.status_code == 422


def test_route_direct_line_fallback(client):
    """Verify safe destination selection, direct line geometry, and map URLs."""
    # Adyar representative point (Saidapet)
    resp = client.get("/api/route?lat=13.015&lng=80.225&mode=walk")
    assert resp.status_code == 200
    data = resp.json()

    assert data["kind"] == "direct_line"
    assert data["provider"] == "direct_line"
    assert data["attribution"] is None  # Attribution string present ONLY when road_route is returned
    assert data["distance_m"] > 0.0

    # Destination shelter
    dest = data["destination"]
    assert dest is not None
    assert dest["shelter_id"].startswith("sh_")
    assert dest["name"] is not None
    assert dest["is_safe"] is True
    assert 0.0 <= dest["bearing_deg"] < 360.0
    assert dest["compass_direction"] in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

    # Alternatives (max 2)
    assert len(data["alternatives"]) <= 2
    for alt in data["alternatives"]:
        assert alt["is_safe"] is True

    # Geometry LineString
    geom = data["geometry"]
    assert geom["type"] == "LineString"
    assert len(geom["coordinates"]) == 2
    assert geom["coordinates"][0] == [80.225, 13.015]

    # Universal Maps URLs
    urls = data["maps_urls"]
    assert urls is not None
    assert "https://www.google.com/maps/dir/?api=1" in urls["google"]
    assert "origin=13.0150,80.2250" in urls["google"]
    assert "travelmode=walking" in urls["google"]

    assert "https://maps.apple.com/" in urls["apple"]
    assert "saddr=13.0150,80.2250" in urls["apple"]
    assert "dirflg=w" in urls["apple"]

    assert urls["geo"].startswith("geo:")

    # Warnings
    assert any(w["key"] == "routing_unavailable" for w in data["warnings"])


def test_route_replay_golden_moment(client):
    """Verify route evaluation during scenario replay at golden_moment."""
    # 1. Start replay scenario and seek to golden_moment
    client.post("/api/scenario/start", json={"name": "michaung_replay", "speed": 1.0})
    client.post("/api/scenario/seek", json={"bookmark": "golden_moment"})

    resp = client.get("/api/route?lat=13.015&lng=80.225")
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_replay"] is True
    assert data["mode_of_data"] == "replay"
    assert data["destination"] is not None
    assert data["destination"]["is_safe"] is True

    # Reset
    client.post("/api/scenario/reset")


def test_route_rate_limiting_per_client(client):
    """Verify 429 Too Many Requests after 30 requests per minute."""
    for i in range(30):
        resp = client.get("/api/route?lat=13.015&lng=80.225&device_id=test-dev-rate")
        assert resp.status_code == 200

    # 31st request should be rejected with 429
    resp_limit = client.get("/api/route?lat=13.015&lng=80.225&device_id=test-dev-rate")
    assert resp_limit.status_code == 429
    assert "Retry-After" in resp_limit.headers
    assert "Rate limit exceeded" in resp_limit.json()["detail"]


def test_route_caching_and_bypass_on_reroute(client):
    """Verify caching on identical queries and bypass when reroute=true."""
    resp1 = client.get("/api/route?lat=13.015&lng=80.225")
    assert resp1.status_code == 200
    r1_id = resp1.json()["route_id"]

    # Same request within TTL should hit cache and return same route_id
    resp2 = client.get("/api/route?lat=13.015&lng=80.225")
    assert resp2.status_code == 200
    assert resp2.json()["route_id"] == r1_id

    # Reroute=true bypasses cache and generates new route_id
    resp3 = client.get("/api/route?lat=13.015&lng=80.225&reroute=true")
    assert resp3.status_code == 200
    assert resp3.json()["route_id"] != r1_id
