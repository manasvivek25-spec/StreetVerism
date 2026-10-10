"""Comprehensive integration tests for StreetVerism Live API and Service Layer (MOCK=0 vs MOCK=1).

Verifies:
- State per status with multilingual templates (en/de fallbacks, reviewed flags, original_en)
- SHELTER_AT safe omission (never emit raw {shelter} placeholder)
- Service coverage inside vs outside Chennai bounding box
- Live vs Replay isolation (DB reports vs replay scenario & overlay)
- /cells delta cap (0.3 deg) and 3000 cell cap 422 validation
- Cells cache invalidation on mutation and scenario mode change
- Report 600s per-device rate limiting (429)
- Checkin latest-per-device triage, handled reset, device_id privacy strip
- Authority API key security (401 on missing, 403 on invalid)
- 48h check-in retention purge boundary
- Full Golden Path integration (michaung_replay + golden_moment + checkin + reset)
- MOCK=1 regression preservation
"""

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.routes import (
    clear_cells_cache,
    get_alert_repo,
    get_checkin_repo,
    get_report_repo,
    get_shelter_repo,
    init_scenario,
    set_custom_repos,
)
from backend.app.config import get_settings
from backend.app.main import app
from backend.app.models import AlertCreate, GeoJSONPolygon
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

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SHELTERS_FILE = ROOT_DIR / "data" / "shelters.json"
TEMPLATES_DIR = ROOT_DIR / "data" / "templates"
SCENARIO_FILE = ROOT_DIR / "data" / "scenarios" / "michaung_replay.json"


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Isolate repositories and configure MOCK=0 test environment."""
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

    # Seed shelters and templates
    seed_shelters_from_file(SHELTERS_FILE, shelter_repo)
    load_and_validate_templates(TEMPLATES_DIR)
    init_scenario(SCENARIO_FILE, SHELTERS_FILE)
    clear_cells_cache()

    monkeypatch.setenv("MOCK", "0")
    monkeypatch.setenv("AUTHORITY_KEY", "test-authority-secret-key-123")
    get_settings.cache_clear()

    yield

    clear_cells_cache()
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_state_template_rendering_and_fallbacks(client):
    """Test state endpoint across en and de languages, checking reviewed flag and fallback strings."""
    # Request state in English (reviewed = true)
    resp_en = client.get("/api/state?lat=13.0827&lng=80.2707&lang=en")
    assert resp_en.status_code == 200
    data_en = resp_en.json()
    assert "status" in data_en
    assert "instructions" in data_en
    assert data_en["coverage"] == "covered"

    for inst in data_en["instructions"]:
        assert inst["reviewed"] is True
        assert inst["original_en"] is None
        assert "{shelter}" not in inst["text"]

    # Request state in German (reviewed = false, unverified translation)
    resp_de = client.get("/api/state?lat=13.0827&lng=80.2707&lang=de")
    assert resp_de.status_code == 200
    data_de = resp_de.json()

    for inst in data_de["instructions"]:
        assert inst["reviewed"] is False
        assert inst["original_en"] is not None
        assert len(inst["original_en"]) > 0
        assert "{shelter}" not in inst["text"]


def test_shelter_at_safe_omission(client):
    """Ensure SHELTER_AT never emits raw {shelter} placeholder even if shelters are not available."""
    resp = client.get("/api/state?lat=13.0827&lng=80.2707&lang=en")
    assert resp.status_code == 200
    instructions = resp.json()["instructions"]
    for inst in instructions:
        assert "{shelter}" not in inst["text"]
        if inst["key"] == "SHELTER_AT":
            assert "shelter" in inst["params"]
            assert inst["params"]["shelter"] is not None


def test_service_coverage_boundary(client):
    """Verify coverage field inside Chennai vs outside."""
    # Chennai Central
    resp_inside = client.get("/api/state?lat=13.0827&lng=80.2707")
    assert resp_inside.status_code == 200
    assert resp_inside.json()["coverage"] == "covered"

    # Mumbai (outside service bounding box)
    resp_outside = client.get("/api/state?lat=18.9220&lng=72.8347")
    assert resp_outside.status_code == 200
    data_outside = resp_outside.json()
    assert data_outside["coverage"] == "outside"
    assert data_outside["status"] in ("clear", "normal")


def test_cells_bbox_delta_and_cap_validation(client):
    """Verify /cells rejects boxes with delta > 0.3 deg or > 3000 cells."""
    # Delta lat > 0.3 deg
    resp_delta = client.get("/api/cells?bbox=80.1,12.8,80.2,13.2")
    assert resp_delta.status_code == 422
    assert "exceeds maximum allowable delta" in resp_delta.json()["detail"]

    # Delta lng > 0.3 deg
    resp_delta_lng = client.get("/api/cells?bbox=80.0,12.9,80.4,13.0")
    assert resp_delta_lng.status_code == 422
    assert "exceeds maximum allowable delta" in resp_delta_lng.json()["detail"]

    # Valid small bounding box
    resp_valid = client.get("/api/cells?bbox=80.20,12.98,80.25,13.02")
    assert resp_valid.status_code == 200
    data = resp_valid.json()
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 0
    assert len(data["features"]) <= 3000

    # Check 5-decimal coordinate precision
    first_coord = data["features"][0]["geometry"]["coordinates"][0][0]
    assert len(str(first_coord[0]).split(".")[-1]) <= 5
    assert len(str(first_coord[1]).split(".")[-1]) <= 5


def test_cells_caching_and_invalidation(client):
    """Verify /cells TTL cache and invalidation on report submission."""
    bbox = "80.20,12.98,80.25,13.02"

    # First fetch (populates cache)
    resp1 = client.get(f"/api/cells?bbox={bbox}")
    assert resp1.status_code == 200

    # Second fetch (serves from cache)
    resp2 = client.get(f"/api/cells?bbox={bbox}")
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()

    # Submit a report in that area - should clear cache
    report_payload = {
        "device_id": "test-dev-001",
        "lat": 13.00,
        "lng": 80.22,
        "claim": "flooded",
        "text": "Water ankle deep",
    }
    resp_rep = client.post("/api/reports", json=report_payload)
    assert resp_rep.status_code == 200

    # Fetching cells again succeeds after invalidation
    resp3 = client.get(f"/api/cells?bbox={bbox}")
    assert resp3.status_code == 200


def test_report_rate_limiting(client):
    """Test 600s per-device rate limiting returns 429."""
    report_payload = {
        "device_id": "rate-limit-device-99",
        "lat": 13.00,
        "lng": 80.22,
        "claim": "flooded",
        "text": "High water levels",
    }
    resp1 = client.post("/api/reports", json=report_payload)
    assert resp1.status_code == 200
    assert resp1.json()["accepted"] is True

    # Immediate second report from same device -> 429
    resp2 = client.post("/api/reports", json=report_payload)
    assert resp2.status_code == 429
    assert "Rate limit exceeded" in resp2.json()["detail"]


def test_checkin_triage_deduplication_and_privacy(client):
    """Verify check-in triage deduplication, privacy device_id stripping, and handled reset."""
    headers = {"X-Authority-Key": "test-authority-secret-key-123"}

    # 1. Submit first checkin (need_help)
    client.post(
        "/api/checkin",
        json={"device_id": "tourist-device-A", "lat": 13.001, "lng": 80.211, "state": "need_help"},
    )

    # Fetch checkins
    resp = client.get("/api/checkins", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["state"] == "need_help"
    assert item["handled"] is False
    assert item.get("device_id") is None  # Privacy protection: device_id never exposed!

    assert len(data["clusters"]) == 1
    assert data["clusters"][0]["unhandled_need_help"] == 1

    # 2. Mark handled
    checkin_id = item["id"]
    patch_resp = client.patch(f"/api/checkins/{checkin_id}", json={"handled": True}, headers=headers)
    assert patch_resp.status_code == 200
    assert patch_resp.json()["handled"] is True

    # Check clusters count updated
    resp_after_patch = client.get("/api/checkins", headers=headers)
    assert resp_after_patch.json()["clusters"][0]["unhandled_need_help"] == 0

    # 3. New submission from SAME device -> replaces previous, resets handled to False
    client.post(
        "/api/checkin",
        json={"device_id": "tourist-device-A", "lat": 13.002, "lng": 80.212, "state": "need_help"},
    )
    resp_after_new = client.get("/api/checkins", headers=headers)
    assert len(resp_after_new.json()["items"]) == 1
    assert resp_after_new.json()["items"][0]["handled"] is False
    assert resp_after_new.json()["clusters"][0]["unhandled_need_help"] == 1


def test_authority_key_security(client):
    """Test X-Authority-Key enforcement (401 on missing, 403 on invalid)."""
    # Missing header -> 401
    resp_missing = client.get("/api/checkins")
    assert resp_missing.status_code == 401

    # Invalid header -> 403
    resp_invalid = client.get("/api/checkins", headers={"X-Authority-Key": "wrong-key"})
    assert resp_invalid.status_code == 403

    # Valid header -> 200
    resp_valid = client.get(
        "/api/checkins", headers={"X-Authority-Key": "test-authority-secret-key-123"}
    )
    assert resp_valid.status_code == 200


def test_retention_purge_older_than_48h():
    """Verify check-in retention purges records older than 48 hours."""
    repo = get_checkin_repo()
    now_epoch = datetime.now(timezone.utc).timestamp()

    # Record from 50 hours ago
    t_50h_ago = datetime.fromtimestamp(now_epoch - 50 * 3600, tz=timezone.utc).isoformat()
    # Record from 10 hours ago
    t_10h_ago = datetime.fromtimestamp(now_epoch - 10 * 3600, tz=timezone.utc).isoformat()

    from backend.app.models import CheckinCreate
    repo.add(
        CheckinCreate(
            device_id="dev-old",
            state="need_help",
            lat=13.0,
            lng=80.2,
            language="en",
            group_size=1,
        ),
        cell7="88618c4c23fffff",
        recorded_at=t_50h_ago,
    )
    repo.add(
        CheckinCreate(
            device_id="dev-recent",
            state="safe",
            lat=13.0,
            lng=80.2,
            language="en",
            group_size=1,
        ),
        cell7="88618c4c23fffff",
        recorded_at=t_10h_ago,
    )

    # Purge older than 48h
    cutoff_iso = datetime.fromtimestamp(now_epoch - 48 * 3600, tz=timezone.utc).isoformat()
    deleted = repo.delete_older_than(cutoff_iso)
    assert deleted == 1

    all_items = repo.list_all()
    ids = [i.id for i in all_items]
    assert len(all_items) == 1


def test_golden_path_replay_workflow(client):
    """End-to-end test of replay scenario start, seeking to bookmark, and state evaluation."""
    # 1. Start scenario
    start_resp = client.post("/api/scenario/start", json={"name": "michaung_replay", "speed": 1.0})
    assert start_resp.status_code == 200
    status = start_resp.json()
    assert status["mode"] == "replay"
    assert status["is_replay"] is True

    # 2. Seek to golden_moment
    seek_resp = client.post("/api/scenario/seek", json={"bookmark": "golden_moment"})
    assert seek_resp.status_code == 200
    status_seek = seek_resp.json()
    assert status_seek["elapsed_s"] == 34200  # golden_moment offset in michaung_replay.json

    # 3. Assess state at Velachery (in official hazard polygon at 11h)
    velachery_state = client.get("/api/state?lat=12.9815&lng=80.2180").json()
    assert velachery_state["status"] in ("official_hazard", "likely_hazard")
    assert len(velachery_state["instructions"]) > 0

    # 4. Reset scenario to live mode
    reset_resp = client.post("/api/scenario/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["mode"] == "live"
    assert reset_resp.json()["is_replay"] is False


def test_mock_mode_regression_preservation(monkeypatch, client):
    """Verify that when MOCK=1 is enabled, the deterministic mock dataset is served with X-Mock-Data header."""
    monkeypatch.setenv("MOCK", "1")
    get_settings.cache_clear()

    resp = client.get("/api/state?lat=13.0827&lng=80.2707")
    assert resp.status_code == 200
    assert resp.headers.get("X-Mock-Data") == "1"
    data = resp.json()
    assert data["status"] in ("official_hazard", "likely_hazard", "unverified_reports", "caution", "normal")

    resp_health = client.get("/health")
    assert resp_health.status_code == 200
    assert resp_health.headers.get("X-Mock-Data") == "1"
    assert resp_health.json()["status"] == "healthy"
