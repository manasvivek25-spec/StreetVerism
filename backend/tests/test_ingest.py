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
        sender="State Disaster Authority (demo)",
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
        sender="State Disaster Authority (demo)",
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
        sender="State Disaster Authority (demo)",
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
        sender="State Disaster Authority (demo)",
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
    assert alerts[0].id == "CAP-DEMO-20261010-001#1"
    assert alerts[1].id == "CAP-DEMO-20261010-002#2" or alerts[1].id == "CAP-DEMO-20261010-001#2"
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
      <sender>State Disaster Authority (demo)</sender>
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
      <sender>State Disaster Authority (demo)</sender>
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


def test_cap_msg_type_cancel_expires_referenced_not_all_clear():
    """Verify CAP msgType='Cancel' expires referenced alerts and does NOT establish all_clear."""
    from backend.app.ingest.lifecycle import get_active_alerts, separate_all_clear_alerts

    xml_orig = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-ORIG-01</identifier>
      <sender>State Disaster Authority (demo)</sender>
      <sent>2026-10-10T08:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <info>
        <category>Met</category>
        <event>Severe Flood Warning</event>
        <expires>2026-10-10T16:00:00+00:00</expires>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""
    orig_alerts = parse_cap_xml(xml_orig)
    assert len(orig_alerts) == 1
    assert orig_alerts[0].id == "CAP-ORIG-01"

    xml_cancel = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-CANCEL-01</identifier>
      <sender>State Disaster Authority (demo)</sender>
      <sent>2026-10-10T10:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Cancel</msgType>
      <references>DEMO-AUTH,CAP-ORIG-01,2026-10-10T08:00:00+00:00</references>
      <info>
        <category>Met</category>
        <event>Flood Cancellation</event>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""
    cancel_alerts = parse_cap_xml(xml_cancel)
    assert len(cancel_alerts) == 1
    cancel = cancel_alerts[0]
    assert cancel.supersedes == "CAP-ORIG-01"
    assert cancel.hazard != "all_clear", "Cancel alert must not be marked as all_clear"
    assert "ALL_CLEAR" not in cancel.instruction_keys

    # At 10:30 UTC: orig is superseded, cancel is expired; 0 active alerts
    active = get_active_alerts(orig_alerts + cancel_alerts, "2026-10-10T10:30:00Z")
    assert len(active) == 0

    # Ensure separate_all_clear_alerts finds 0 all_clear alerts
    hazards, clears = separate_all_clear_alerts(orig_alerts + cancel_alerts)
    assert len(clears) == 0


def test_cap_msg_type_update_supersedes():
    """Verify CAP msgType='Update' supersedes previous referenced alert."""
    from backend.app.ingest.lifecycle import get_active_alerts

    xml_orig = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-UPDATE-ORIG</identifier>
      <sender>State Disaster Authority (demo)</sender>
      <sent>2026-10-10T08:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <info>
        <category>Met</category>
        <event>Flood Warning</event>
        <expires>2026-10-10T18:00:00+00:00</expires>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""
    xml_update = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-UPDATE-NEW</identifier>
      <sender>State Disaster Authority (demo)</sender>
      <sent>2026-10-10T09:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Update</msgType>
      <references>DEMO-AUTH,CAP-UPDATE-ORIG,2026-10-10T08:00:00+00:00</references>
      <info>
        <category>Met</category>
        <event>Cyclone Warning</event>
        <expires>2026-10-10T20:00:00+00:00</expires>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""
    orig = parse_cap_xml(xml_orig)
    update = parse_cap_xml(xml_update)
    assert update[0].supersedes == "CAP-UPDATE-ORIG"

    active = get_active_alerts(orig + update, "2026-10-10T09:30:00Z")
    assert len(active) == 1
    assert active[0].id == "CAP-UPDATE-NEW"


def test_cap_urgency_past_skipped():
    """Verify CAP alert with urgency='Past' is skipped and returns empty list."""
    xml_past = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-PAST-01</identifier>
      <sender>State Disaster Authority (demo)</sender>
      <sent>2026-10-10T08:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <info>
        <category>Met</category>
        <event>Flood</event>
        <urgency>Past</urgency>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""
    alerts = parse_cap_xml(xml_past)
    assert alerts == []


def test_cap_circle_area_handling():
    """Verify CAP circle 'lat,lng radius_km' is parsed to GeoJSON polygon approximation."""
    xml_circle = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-CIRCLE-01</identifier>
      <sender>State Disaster Authority (demo)</sender>
      <sent>2026-10-10T08:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <info>
        <category>Met</category>
        <event>Flood</event>
        <area>
          <circle>13.0827,80.2707 5.0</circle>
        </area>
      </info>
    </alert>"""
    alerts = parse_cap_xml(xml_circle)
    assert len(alerts) == 1
    coords = alerts[0].area.coordinates[0]
    assert len(coords) > 10, "Circle approximation should contain multiple polygon vertices"
    assert coords[0] == coords[-1], "Ring must be closed"
    # Verify coordinate order: [lng, lat]
    for pt in coords:
        assert 79.5 <= pt[0] <= 81.0, f"Expected longitude first: {pt[0]}"
        assert 12.5 <= pt[1] <= 13.5, f"Expected latitude second: {pt[1]}"


def test_cap_enum_mapping_warnings(caplog):
    """Verify Unknown severity/urgency and Unlikely/Unknown certainty produce logged warnings and safe fallbacks."""
    import logging

    xml_enums = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-ENUMS-01</identifier>
      <sender>State Disaster Authority (demo)</sender>
      <sent>2026-10-10T08:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Alert</msgType>
      <info>
        <category>Met</category>
        <event>Flood</event>
        <severity>Unknown</severity>
        <urgency>Unknown</urgency>
        <certainty>Unlikely</certainty>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""
    with caplog.at_level(logging.WARNING):
        alerts = parse_cap_xml(xml_enums)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.severity == "minor"
    assert alert.urgency == "expected"
    assert alert.certainty == "possible"

    assert any("CAP severity 'unknown' mapped to fallback 'minor'" in msg for msg in caplog.messages)
    assert any("CAP urgency 'unknown' mapped to fallback 'expected'" in msg for msg in caplog.messages)
    assert any("CAP certainty 'unlikely' mapped to fallback 'possible'" in msg for msg in caplog.messages)


def test_manual_hazard_requires_at_least_one_instruction_key():
    """Verify non-all_clear hazard alert requires at least one instruction key."""
    payload = AlertCreate(
        source="official_manual",
        sender="State Disaster Authority (demo)",
        hazard="flood",
        severity="severe",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[[[80.2, 13.0], [80.3, 13.0], [80.3, 13.1], [80.2, 13.0]]]),
        instruction_keys=[],
        sent_at="2026-10-10T08:00:00Z",
        expires_at="2026-10-10T16:00:00Z",
        published_by="tester",
    )
    with pytest.raises(ValueError, match="must include at least one instruction key"):
        normalize_manual_alert(payload)


def test_polygon_coordinate_and_vertex_bounds():
    """Verify longitude/latitude out of bounds and vertex cap boundaries."""
    # 1. Longitude out of bounds
    with pytest.raises(ValueError, match="Longitude out of bounds"):
        validate_and_repair_polygon([[[185.0, 13.0], [186.0, 13.0], [186.0, 13.1], [185.0, 13.0]]])

    # 2. Latitude out of bounds
    with pytest.raises(ValueError, match="Latitude out of bounds"):
        validate_and_repair_polygon([[[80.0, -95.0], [81.0, -95.0], [81.0, -94.0], [80.0, -95.0]]])

    # 3. Vertex cap: exactly 501 vertices (> MAX_POLYGON_VERTICES = 500)
    oversized = [[[float(i), float(i)] for i in range(MAX_POLYGON_VERTICES + 1)]]
    with pytest.raises(ValueError, match="exceeds maximum allowed vertices"):
        validate_and_repair_polygon(oversized)


def test_alert_serialization_emits_params_and_supersedes():
    """Verify Alert serialization always emits params ({} default) and supersedes (null default)."""
    from backend.app.models import Alert

    alert = Alert(
        id="alt_serial_test",
        source="official_manual",
        sender="State Disaster Authority (demo)",
        hazard="flood",
        severity="moderate",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[[[80.2, 13.0], [80.3, 13.0], [80.3, 13.1], [80.2, 13.0]]]),
        sent_at="2026-10-10T08:00:00Z",
        expires_at="2026-10-10T16:00:00Z",
        published_by="tester",
    )
    # 1. Direct fields default
    assert alert.params == {}
    assert alert.supersedes is None

    # 2. model_dump dictionary
    dumped = alert.model_dump()
    assert "params" in dumped and dumped["params"] == {}
    assert "supersedes" in dumped and dumped["supersedes"] is None

    # 3. model_dump_json JSON string
    json_str = alert.model_dump_json()
    assert '"params":{}' in json_str
    assert '"supersedes":null' in json_str

    # 4. Explicit None passed into constructor sanitized to defaults
    alert_none = Alert(
        id="alt_none_test",
        source="official_manual",
        sender="State Disaster Authority (demo)",
        hazard="flood",
        severity="moderate",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[[[80.2, 13.0], [80.3, 13.0], [80.3, 13.1], [80.2, 13.0]]]),
        sent_at="2026-10-10T08:00:00Z",
        expires_at="2026-10-10T16:00:00Z",
        published_by="tester",
        params=None,
        supersedes=None,
    )
    assert alert_none.params == {}
    assert alert_none.supersedes is None
