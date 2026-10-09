"""Tests for SQLite persistence layer, idempotency, coordinate rounding, and repositories."""

import os
import tempfile
import pytest

from backend.app.db import get_db_connection, init_db, to_utc_iso
from backend.app.models import (
    Alert,
    CheckinCreate,
    GeoJSONPolygon,
    ReportCreate,
    Shelter,
)
from backend.app.repositories import (
    InMemoryAlertRepo,
    InMemoryCheckinRepo,
    InMemoryReportRepo,
    InMemoryShelterRepo,
    SqliteAlertRepo,
    SqliteCheckinRepo,
    SqliteReportRepo,
    SqliteShelterRepo,
)


@pytest.fixture
def temp_db_path():
    """Create a temporary SQLite database file for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_init_db_idempotency(temp_db_path):
    """Verify init_db can be called multiple times without error or schema corruption."""
    init_db(temp_db_path)
    init_db(temp_db_path)  # Idempotent second call
    with get_db_connection(temp_db_path) as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ).fetchall()
        table_names = [r["name"] for r in tables]
        assert "alerts" in table_names
        assert "reports" in table_names
        assert "checkins" in table_names
        assert "shelters" in table_names


def test_timestamp_normalization_on_write(temp_db_path):
    """Verify non-conforming timestamps with timezone offsets are normalized to fixed UTC ISO string on write."""
    init_db(temp_db_path)
    repo = SqliteAlertRepo(temp_db_path)

    # Offset timestamp
    non_conforming_sent = "2026-10-10T15:30:00+05:30"  # Equals 10:00:00 UTC
    non_conforming_exp = "2026-10-10T23:30:00+05:30"   # Equals 18:00:00 UTC

    alert = Alert(
        id="alt_test_tz",
        source="official_manual",
        sender="TNSDMA (demo)",
        hazard="flood",
        severity="extreme",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[[[80.2, 13.0], [80.25, 13.0], [80.25, 13.05], [80.2, 13.05], [80.2, 13.0]]]),
        instruction_keys=["MOVE_TO_HIGHER_GROUND"],
        params={},
        sent_at=non_conforming_sent,
        expires_at=non_conforming_exp,
        published_by="tester",
        is_replay=False,
    )
    saved = repo.add(alert)
    assert saved.sent_at == "2026-10-10T10:00:00.000000Z"
    assert saved.expires_at == "2026-10-10T18:00:00.000000Z"

    # Query from raw SQL to verify stored format
    with get_db_connection(temp_db_path) as conn:
        row = conn.execute("SELECT sent_at, expires_at FROM alerts WHERE id = 'alt_test_tz'").fetchone()
        assert row["sent_at"] == "2026-10-10T10:00:00.000000Z"
        assert row["expires_at"] == "2026-10-10T18:00:00.000000Z"


def test_coordinate_privacy_rounding(temp_db_path):
    """Verify report and checkin coordinates are rounded to exactly 4 decimal places at write time."""
    init_db(temp_db_path)
    report_repo = SqliteReportRepo(temp_db_path)
    checkin_repo = SqliteCheckinRepo(temp_db_path)

    # 6 decimals
    high_prec_lat = 13.082736
    high_prec_lng = 80.270749

    rep = report_repo.add(
        ReportCreate(device_id="uuid-1", lat=high_prec_lat, lng=high_prec_lng, claim="flooded"),
        cell="88618c4885fffff",
    )
    assert rep["lat"] == 13.0827
    assert rep["lng"] == 80.2707

    chk = checkin_repo.add(
        CheckinCreate(device_id="uuid-1", lat=high_prec_lat, lng=high_prec_lng, state="safe"),
        cell7="87618c488ffffff",
    )
    assert chk.lat == 13.0827
    assert chk.lng == 80.2707


def test_shelter_crud_and_in_memory_parity(temp_db_path):
    """Verify shelters SQLite and InMemory repos behave identically."""
    init_db(temp_db_path)
    sqlite_repo = SqliteShelterRepo(temp_db_path)
    in_mem_repo = InMemoryShelterRepo()

    shelter = Shelter(
        id="sh_test",
        name="Test Relief Hall",
        name_local="சோதனை நிவாரண கூடம்",
        lat=13.04,
        lng=80.23,
        open=True,
        is_demo=True,
        capacity=200,
    )

    sqlite_repo.add(shelter)
    in_mem_repo.add(shelter)

    s1 = sqlite_repo.get("sh_test")
    s2 = in_mem_repo.get("sh_test")

    assert s1 is not None and s2 is not None
    assert s1.id == s2.id == "sh_test"
    assert s1.capacity == s2.capacity == 200
