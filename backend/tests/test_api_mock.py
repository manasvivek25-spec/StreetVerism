"""Comprehensive test suite verifying all StreetVerism mock API contracts."""

import pytest
from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app

client = TestClient(app)


def auth_headers():
    return {"X-Authority-Key": get_settings().authority_key}


def test_missing_authority_key_fails_fast(monkeypatch):
    """Verify system fails fast with clear RuntimeError if AUTHORITY_KEY is missing."""
    monkeypatch.delenv("AUTHORITY_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="CRITICAL SECURITY ERROR"):
        get_settings()
    # Restore key for subsequent tests
    monkeypatch.setenv("AUTHORITY_KEY", "test-env-authority-key")
    get_settings.cache_clear()


def test_health_endpoints():
    """Verify both /health and /api/health respond with server_time."""
    for path in ["/health", "/api/health"]:
        res = client.get(path)
        assert res.status_code == 200, f"Failed at {path}"
        data = res.json()
        assert data["status"] == "healthy"
        assert "server_time" in data
        assert "mode" in data
        assert "version" in data


def test_mock_mode_header_and_mode_switching(monkeypatch):
    """Verify: with MOCK=1, /health returns mode 'mock' and X-Mock-Data: 1 is present; with MOCK=0, header is absent."""
    # Test MOCK=1
    monkeypatch.setenv("MOCK", "1")
    get_settings.cache_clear()
    res_mock = client.get("/health")
    assert res_mock.status_code == 200
    assert res_mock.json()["mode"] == "mock"
    assert res_mock.headers.get("X-Mock-Data") == "1"

    res_api_mock = client.get("/api/health")
    assert res_api_mock.status_code == 200
    assert res_api_mock.json()["mode"] == "mock"
    assert res_api_mock.headers.get("X-Mock-Data") == "1"

    # Test MOCK=0
    monkeypatch.setenv("MOCK", "0")
    get_settings.cache_clear()
    res_live = client.get("/health")
    assert res_live.status_code == 200
    assert res_live.json()["mode"] == "live"
    assert "X-Mock-Data" not in res_live.headers

    res_api_live = client.get("/api/health")
    assert res_api_live.status_code == 200
    assert res_api_live.json()["mode"] == "live"
    assert "X-Mock-Data" not in res_api_live.headers

    # Reset back to MOCK=1
    monkeypatch.setenv("MOCK", "1")
    get_settings.cache_clear()


def test_state_endpoint_english():
    """Verify /api/state returns complete tourist payload in English."""
    res = client.get("/api/state?lat=13.04&lng=80.23&lang=en")
    assert res.status_code == 200
    data = res.json()
    assert "cell" in data
    assert data["status"] == "official_hazard"
    assert data["p_hazard"] >= 0.0
    assert data["headline_key"] == "MOVE_TO_HIGHER_GROUND"
    assert "alerts" in data
    assert len(data["instructions"]) > 0
    assert all(inst["reviewed"] is True for inst in data["instructions"])
    assert len(data["evidence"]) > 0
    assert len(data["nearest_shelters"]) > 0
    assert "server_time" in data
    assert "generated_at" in data


def test_state_endpoint_machine_translated():
    """Verify unreviewed languages (e.g. German) include machine-translated notice flag and original English."""
    res = client.get("/api/state?lat=13.04&lng=80.23&lang=de")
    assert res.status_code == 200
    data = res.json()
    assert len(data["instructions"]) > 0
    for inst in data["instructions"]:
        assert inst["reviewed"] is False
        assert inst["original_en"] is not None
        assert len(inst["original_en"]) > 0


def test_cells_endpoint_contains_all_five_statuses():
    """Verify /api/cells mock dataset contains all five specified cell statuses."""
    res = client.get("/api/cells?bbox=80.20,12.95,80.26,13.05")
    assert res.status_code == 200
    data = res.json()
    assert data["type"] == "FeatureCollection"
    features = data["features"]
    assert len(features) >= 5

    statuses = {f["properties"]["status"] for f in features}
    required_statuses = {"official_hazard", "likely_hazard", "unverified", "contradicted", "clear"}
    missing = required_statuses - statuses
    assert not missing, f"Missing statuses in /api/cells mock: {missing}"

    # Verify GeoJSON polygon format
    for f in features:
        geom = f["geometry"]
        assert geom["type"] == "Polygon"
        ring = geom["coordinates"][0]
        assert ring[0] == ring[-1], "GeoJSON linear ring must be closed"
        for pt in ring:
            assert len(pt) == 2
            # pt is [lng, lat]
            lng, lat = pt
            assert 80.0 <= lng <= 81.0
            assert 12.0 <= lat <= 14.0


def test_shelters_endpoint():
    """Verify /api/shelters returns enveloped list with total count."""
    res = client.get("/api/shelters")
    assert res.status_code == 200
    data = res.json()
    assert "shelters" in data
    assert "total" in data
    assert data["total"] == len(data["shelters"])
    assert data["total"] > 0
    shelter = data["shelters"][0]
    assert "id" in shelter
    assert "name" in shelter
    assert "name_local" in shelter
    assert "lat" in shelter
    assert "lng" in shelter
    assert "open" in shelter
    assert shelter["is_demo"] is True


def test_templates_en_has_all_required_keys():
    """Verify /api/templates/en has every template key from the hackathon brief."""
    res = client.get("/api/templates/en")
    assert res.status_code == 200
    data = res.json()
    assert data["lang"] == "en"
    assert data["reviewed"] is True
    templates = data["templates"]

    required_keys = [
        "MOVE_TO_HIGHER_GROUND",
        "AVOID_FLOODED_ROADS",
        "DO_NOT_CROSS_WATER",
        "SHELTER_AT",
        "STAY_INDOORS",
        "STAY_AWAY_FROM_COAST",
        "KEEP_PHONE_CHARGED",
        "ALL_CLEAR",
        "EMERGENCY_NUMBER",
        "FOLLOW_OFFICIAL_ONLY",
        "CHECKIN_PROMPT",
        "UNVERIFIED_WARNING",
    ]
    for key in required_keys:
        assert key in templates, f"Missing template key: {key}"


def test_reports_submission():
    """Verify POST /api/reports accepts crowd claims and assigns cell."""
    payload = {
        "device_id": "4e75618b-8219-4cb3-a551-766cf0180a22",
        "lat": 13.04,
        "lng": 80.23,
        "claim": "flooded",
        "text": "Water ankle deep and rising fast near market",
    }
    res = client.post("/api/reports", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is True
    assert "cell" in data
    assert data["status"] == "unverified"


def test_checkin_submission():
    """Verify POST /api/checkin logs tourist status and returns confirmation."""
    payload = {
        "device_id": "9bc27993-9cbf-4882-a392-581335cfa32e",
        "lat": 12.9815,
        "lng": 80.2180,
        "state": "need_help",
        "language": "de",
        "group_size": 2,
        "note": "Elderly passenger, need evacuation boat",
    }
    res = client.post("/api/checkin", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert "recorded_at" in data


def test_authority_authentication_guards():
    """Verify X-Authority-Key header is strictly enforced on administrative endpoints."""
    # Without header -> 401
    res = client.get("/api/alerts")
    assert res.status_code == 401

    # With invalid header -> 403
    res = client.get("/api/alerts", headers={"X-Authority-Key": "wrong-secret"})
    assert res.status_code == 403

    # With valid header -> 200
    res = client.get("/api/alerts", headers=auth_headers())
    assert res.status_code == 200


def test_authority_alerts_crud():
    """Verify alert publishing, listing, and expiry."""
    # List alerts
    res = client.get("/api/alerts", headers=auth_headers())
    assert res.status_code == 200
    initial_total = res.json()["total"]

    # Publish alert
    new_alert = {
        "source": "official_manual",
        "sender": "TNSDMA (demo)",
        "hazard": "flood",
        "severity": "extreme",
        "urgency": "immediate",
        "certainty": "observed",
        "area": {
            "type": "Polygon",
            "coordinates": [
                [
                    [80.20, 13.00],
                    [80.25, 13.00],
                    [80.25, 13.05],
                    [80.20, 13.05],
                    [80.20, 13.00],
                ]
            ],
        },
        "instruction_keys": ["MOVE_TO_HIGHER_GROUND"],
        "params": {},
        "sent_at": "2026-10-10T12:00:00Z",
        "expires_at": "2026-10-10T18:00:00Z",
        "published_by": "test-operator",
        "is_replay": False,
    }
    res_post = client.post("/api/alerts", json=new_alert, headers=auth_headers())
    assert res_post.status_code == 201
    created = res_post.json()
    assert "id" in created
    alert_id = created["id"]

    # Expire alert
    res_del = client.delete(f"/api/alerts/{alert_id}", headers=auth_headers())
    assert res_del.status_code == 200
    assert res_del.json()["ok"] is True


def test_authority_checkins_triage():
    """Verify checkins retrieval and dispatch update."""
    res = client.get("/api/checkins", headers=auth_headers())
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "clusters" in data
    assert len(data["items"]) > 0

    item_id = data["items"][0]["id"]
    res_patch = client.patch(f"/api/checkins/{item_id}", json={"handled": True}, headers=auth_headers())
    assert res_patch.status_code == 200
    assert res_patch.json()["handled"] is True


def test_scenario_controls_and_seek_validation():
    """Verify scenario start, seek XOR validation (422), and reset."""
    # Start scenario
    res_start = client.post("/api/scenario/start", json={"name": "michaung_replay", "speed": 2.0})
    assert res_start.status_code == 200
    status = res_start.json()
    assert status["is_running"] is True
    assert status["mode"] == "replay"
    assert status["is_replay"] is True

    # Seek: Both 't' and 'offset_s' -> 422
    res_both = client.post("/api/scenario/seek", json={"t": "2023-12-04T08:00:00Z", "offset_s": 3600})
    assert res_both.status_code == 422

    # Seek: Neither -> 422
    res_neither = client.post("/api/scenario/seek", json={})
    assert res_neither.status_code == 422

    # Seek: valid offset_s
    res_seek = client.post("/api/scenario/seek", json={"offset_s": 7200})
    assert res_seek.status_code == 200
    assert res_seek.json()["elapsed_s"] == 7200

    # Get status
    res_status = client.get("/api/scenario/status")
    assert res_status.status_code == 200
    assert res_status.json()["mode"] == "replay"

    # Reset
    res_reset = client.post("/api/scenario/reset")
    assert res_reset.status_code == 200
    assert res_reset.json()["mode"] == "live"


def test_stretch_hazard_aware_route():
    """Verify stretch /api/route returns GeoJSON LineString and steps."""
    res = client.get("/api/route?from_lat=13.0&from_lng=80.2&to_shelter=sh_chennai_01&lang=en")
    assert res.status_code == 200
    data = res.json()
    assert "route" in data
    assert data["route"]["type"] == "LineString"
    assert len(data["steps"]) > 0
    assert data["distance_m"] > 0
    assert "hazard_cells_avoided" in data
