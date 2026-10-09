"""Tests for alert normalization: manual publish validation and CAP XML ingestion."""

from pathlib import Path
import pytest
from defusedxml.common import DefusedXmlException, EntitiesForbidden

from backend.app.ingest.cap import parse_cap_xml
from backend.app.ingest.manual import (
    MAX_POLYGON_VERTICES,
    normalize_manual_alert,
    validate_and_repair_polygon,
)
from backend.app.models import AlertCreate, GeoJSONPolygon


def test_manual_alert_valid_normalization():
    """Verify standard manual alert is normalized with UTC ISO timestamps and valid polygon."""
    payload = AlertCreate(
        source="official_manual",
        sender="TNSDMA",
        hazard="flood",
        severity="severe",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(
            coordinates=[[[80.20, 13.00], [80.25, 13.00], [80.25, 13.05], [80.20, 13.05], [80.20, 13.00]]]
        ),
        instruction_keys=["MOVE_TO_HIGHER_GROUND", "AVOID_FLOODED_ROADS"],
        params={},
        sent_at="2026-10-10T08:00:00Z",
        expires_at="2026-10-10T16:00:00Z",
        published_by="console_user",
        is_replay=False,
    )
    alert = normalize_manual_alert(payload)
    assert alert.id.startswith("alt_")
    assert alert.sent_at == "2026-10-10T08:00:00.000000Z"
    assert alert.expires_at == "2026-10-10T16:00:00.000000Z"
    assert alert.instruction_keys == ["MOVE_TO_HIGHER_GROUND", "AVOID_FLOODED_ROADS"]


def test_manual_alert_polygon_auto_repair():
    """Verify self-intersecting bowtie polygon is auto-repaired via buffer(0)."""
    # Self-intersecting bowtie
    bowtie = [[[0.0, 0.0], [2.0, 2.0], [2.0, 0.0], [0.0, 2.0], [0.0, 0.0]]]
    repaired = validate_and_repair_polygon(bowtie)
    assert repaired.coordinates[0][0] == repaired.coordinates[0][-1]


def test_manual_alert_validation_failures():
    """Verify various validation rejection rules."""
    # 1. Invalid coordinates out of bounds
    with pytest.raises(ValueError, match="Latitude out of bounds"):
        validate_and_repair_polygon([[[80.0, 95.0], [81.0, 95.0], [81.0, 96.0], [80.0, 95.0]]])

    # 2. Exceeding max vertices
    huge_ring = [[[float(i), float(i)] for i in range(MAX_POLYGON_VERTICES + 10)]]
    with pytest.raises(ValueError, match="exceeds maximum allowed vertices"):
        validate_and_repair_polygon(huge_ring)

    # 3. sent_at >= expires_at
    payload_bad_time = AlertCreate(
        source="official_manual",
        sender="TNSDMA",
        hazard="flood",
        severity="severe",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[[[80.2, 13.0], [80.3, 13.0], [80.3, 13.1], [80.2, 13.0]]]),
        instruction_keys=["MOVE_TO_HIGHER_GROUND"],
        sent_at="2026-10-10T16:00:00Z",
        expires_at="2026-10-10T10:00:00Z",
        published_by="tester",
    )
    with pytest.raises(ValueError, match="must be strictly earlier than expires_at"):
        normalize_manual_alert(payload_bad_time)

    # 4. Unknown instruction key
    payload_bad_key = AlertCreate(
        source="official_manual",
        sender="TNSDMA",
        hazard="flood",
        severity="severe",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[[[80.2, 13.0], [80.3, 13.0], [80.3, 13.1], [80.2, 13.0]]]),
        instruction_keys=["NON_EXISTENT_KEY"],
        sent_at="2026-10-10T10:00:00Z",
        expires_at="2026-10-10T16:00:00Z",
        published_by="tester",
    )
    with pytest.raises(ValueError, match="Unknown instruction key"):
        normalize_manual_alert(payload_bad_key)

    # 5. all_clear without ALL_CLEAR instruction key
    payload_bad_all_clear = AlertCreate(
        source="official_manual",
        sender="TNSDMA",
        hazard="all_clear",
        severity="minor",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[[[80.2, 13.0], [80.3, 13.0], [80.3, 13.1], [80.2, 13.0]]]),
        instruction_keys=["MOVE_TO_HIGHER_GROUND"],
        sent_at="2026-10-10T10:00:00Z",
        expires_at="2026-10-10T16:00:00Z",
        published_by="tester",
    )
    with pytest.raises(ValueError, match="must include 'ALL_CLEAR' in instruction_keys"):
        normalize_manual_alert(payload_bad_all_clear)


def test_cap_sample_xml_parsing_and_multi_area():
    """Verify backend/mock_data/sample_cap.xml parses into multiple alerts (one per area)."""
    xml_path = Path(__file__).resolve().parent.parent / "mock_data" / "sample_cap.xml"
    with open(xml_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    alerts = parse_cap_xml(xml_content, is_demo=True)
    assert len(alerts) == 2, f"Expected 2 alerts from 2 areas, got {len(alerts)}"
    assert alerts[0].id == "CAP-TNSDMA-20261010-001#1"
    assert alerts[1].id == "CAP-TNSDMA-20261010-002#2" or alerts[1].id == "CAP-TNSDMA-20261010-001#2"
    assert "(demo)" in alerts[0].sender

    # Test coordinate swap: CAP input has lat=12.9750, lng=80.2100
    # GeoJSON output must have pt[0]=lng (~80.21) and pt[1]=lat (~12.975)
    first_pt = alerts[0].area.coordinates[0][0]
    assert 80.20 <= first_pt[0] <= 80.25, f"Expected longitude first: {first_pt}"
    assert 12.95 <= first_pt[1] <= 13.00, f"Expected latitude second: {first_pt}"


def test_cap_timezone_missing_rejected():
    """Verify CAP alert with missing timezone offset is rejected with ValueError."""
    xml_no_tz = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-NO-TZ</identifier>
      <sender>TNSDMA</sender>
      <sent>2026-10-10T08:00:00</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <info>
        <category>Met</category>
        <event>Flood</event>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""
    with pytest.raises(ValueError, match="lacks required timezone offset"):
        parse_cap_xml(xml_no_tz)


def test_cap_non_actual_status_skipped():
    """Verify CAP alerts with status Exercise, Test, or Draft produce empty list."""
    xml_test = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-TEST-001</identifier>
      <sender>TNSDMA</sender>
      <sent>2026-10-10T08:00:00+05:30</sent>
      <status>Exercise</status>
      <msgType>Alert</msgType>
      <info>
        <category>Met</category>
        <event>Flood</event>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""
    alerts = parse_cap_xml(xml_test)
    assert len(alerts) == 0


def test_cap_xxe_and_entity_expansion_rejected():
    """Verify defusedxml rejects XXE external entities and entity expansion (billion laughs)."""
    # 1. XXE External Entity
    xxe_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE alert [
      <!ENTITY xxe SYSTEM "file:///etc/passwd">
    ]>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>&xxe;</identifier>
      <sender>Attacker</sender>
      <sent>2026-10-10T08:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
    </alert>"""
    with pytest.raises((DefusedXmlException, EntitiesForbidden)):
        parse_cap_xml(xxe_payload)

    # 2. Entity expansion / Billion laughs recursion
    expansion_payload = """<?xml version="1.0"?>
    <!DOCTYPE lolz [
      <!ENTITY lol "lol">
      <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
      <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
    ]>
    <alert>
      <identifier>&lol3;</identifier>
      <sender>Attacker</sender>
      <sent>2026-10-10T08:00:00+00:00</sent>
    </alert>"""
    with pytest.raises((DefusedXmlException, EntitiesForbidden)):
        parse_cap_xml(expansion_payload)
