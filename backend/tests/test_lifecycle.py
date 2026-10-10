"""Tests for alert lifecycle: temporal expiry boundaries, supersede chains, cycle guard, and all_clear."""

from datetime import datetime, timezone
import pytest

from backend.app.ingest.lifecycle import (
    expire_alert_now,
    get_active_alerts,
    is_active,
    is_temporally_active,
    resolve_superseded_ids,
    separate_all_clear_alerts,
)
from backend.app.models import Alert, GeoJSONPolygon


def _make_alert(
    alert_id: str,
    sent_at: str,
    expires_at: str,
    hazard: str = "flood",
    supersedes: str = None,
) -> Alert:
    return Alert(
        id=alert_id,
        source="official_manual",
        sender="State Disaster Authority (demo)",
        hazard=hazard,
        severity="severe",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[[[80.2, 13.0], [80.3, 13.0], [80.3, 13.1], [80.2, 13.0]]]),
        instruction_keys=["MOVE_TO_HIGHER_GROUND"] if hazard != "all_clear" else ["ALL_CLEAR"],
        params={},
        sent_at=sent_at,
        expires_at=expires_at,
        supersedes=supersedes,
        published_by="operator",
        is_replay=False,
    )


def test_temporal_boundary_conditions():
    """Verify exact boundaries: sent_at <= now < expires_at."""
    sent = "2026-10-10T10:00:00.000000Z"
    exp = "2026-10-10T18:00:00.000000Z"
    alert = _make_alert("alt_bound", sent, exp)

    # Before sent_at -> False
    assert not is_temporally_active(alert, "2026-10-10T09:59:59.999999Z")

    # Exactly at sent_at -> True
    assert is_temporally_active(alert, "2026-10-10T10:00:00.000000Z")

    # Middle -> True
    assert is_temporally_active(alert, "2026-10-10T14:00:00.000000Z")

    # Exactly at expires_at -> False (half-open interval [sent, exp))
    assert not is_temporally_active(alert, "2026-10-10T18:00:00.000000Z")

    # After expires_at -> False
    assert not is_temporally_active(alert, "2026-10-10T18:00:01.000000Z")


def test_supersede_timing_effective_only_when_sent():
    """Verify that a supersede takes effect ONLY when superseding alert's sent_at <= now."""
    # Alert A is currently active
    a = _make_alert("alt_A", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z")
    # Alert B supersedes A, but B is scheduled in the future at 12:00:00
    b = _make_alert("alt_B", "2026-10-10T12:00:00Z", "2026-10-10T20:00:00Z", supersedes="alt_A")

    alerts = [a, b]

    # At 11:00 (before B is sent): A is active, B has not superseded A yet
    active_at_11 = get_active_alerts(alerts, "2026-10-10T11:00:00Z")
    assert len(active_at_11) == 1
    assert active_at_11[0].id == "alt_A"

    # At 13:00 (after B is sent): B is active, A is superseded
    active_at_13 = get_active_alerts(alerts, "2026-10-10T13:00:00Z")
    assert len(active_at_13) == 1
    assert active_at_13[0].id == "alt_B"


def test_supersede_chain_and_irreversibility():
    """Verify chain A -> B -> C and that A stays superseded even after B expires."""
    # A sent 10:00, expires 14:00
    a = _make_alert("alt_A", "2026-10-10T10:00:00Z", "2026-10-10T14:00:00Z")
    # B sent 11:00, expires 13:00 (expires early!), supersedes A
    b = _make_alert("alt_B", "2026-10-10T11:00:00Z", "2026-10-10T13:00:00Z", supersedes="alt_A")
    # C sent 12:00, expires 18:00, supersedes B
    c = _make_alert("alt_C", "2026-10-10T12:00:00Z", "2026-10-10T18:00:00Z", supersedes="alt_B")

    alerts = [a, b, c]

    # At 13:30: B is now expired. C is active. A must remain superseded (does NOT revive!)
    active_at_1330 = get_active_alerts(alerts, "2026-10-10T13:30:00Z")
    assert len(active_at_1330) == 1
    assert active_at_1330[0].id == "alt_C"

    # At 19:00: All are expired, none active
    active_at_19 = get_active_alerts(alerts, "2026-10-10T19:00:00Z")
    assert len(active_at_19) == 0


def test_supersede_cycle_guard():
    """Verify cycle guard (A supersedes B and B supersedes A) breaks cleanly without crash or infinite loop."""
    # A sent 10:00, supersedes B
    a = _make_alert("alt_A", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z", supersedes="alt_B")
    # B sent 11:00 (later), supersedes A
    b = _make_alert("alt_B", "2026-10-10T11:00:00Z", "2026-10-10T18:00:00Z", supersedes="alt_A")

    alerts = [a, b]
    superseded = resolve_superseded_ids(alerts, "2026-10-10T12:00:00Z")

    # The earlier one (A) should be superseded, the later one (B) preserved
    assert "alt_A" in superseded
    assert "alt_B" not in superseded

    active = get_active_alerts(alerts, "2026-10-10T12:00:00Z")
    assert len(active) == 1
    assert active[0].id == "alt_B"


def test_supersede_unknown_reference():
    """Verify unknown superseded ID is safely ignored with warning and alert remains active."""
    a = _make_alert("alt_A", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z", supersedes="non_existent_id")
    active = get_active_alerts([a], "2026-10-10T12:00:00Z")
    assert len(active) == 1
    assert active[0].id == "alt_A"


def test_separate_all_clear_alerts():
    """Verify hazard alerts and all_clear alerts are segregated for trust engine use."""
    flood_alert = _make_alert("alt_flood", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z", hazard="flood")
    clear_alert = _make_alert("alt_clear", "2026-10-10T12:00:00Z", "2026-10-10T18:00:00Z", hazard="all_clear")

    hazards, clears = separate_all_clear_alerts([flood_alert, clear_alert])
    assert len(hazards) == 1 and hazards[0].id == "alt_flood"
    assert len(clears) == 1 and clears[0].id == "alt_clear"


def test_expire_alert_now():
    """Verify soft expiration sets expires_at to now for audit trail."""
    a = _make_alert("alt_A", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z")
    now_str = "2026-10-10T12:30:00Z"
    expired = expire_alert_now(a, now_str)
    assert expired.expires_at == "2026-10-10T12:30:00.000000Z"
    assert not is_temporally_active(expired, "2026-10-10T12:30:01Z")


def test_cancel_two_area_alert_deactivates_both_polygons():
    """Verify Cancel referencing base identifier deactivates all multi-area polygons ({id}#1, {id}#2)."""
    a1 = _make_alert("alt_multi#1", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z")
    a2 = _make_alert("alt_multi#2", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z")
    cancel = _make_alert("alt_cancel", "2026-10-10T11:00:00Z", "2026-10-10T11:00:00Z", supersedes="alt_multi")

    alerts = [a1, a2, cancel]
    active_before = get_active_alerts(alerts, "2026-10-10T10:30:00Z")
    assert len(active_before) == 2
    assert {a.id for a in active_before} == {"alt_multi#1", "alt_multi#2"}

    active_after = get_active_alerts(alerts, "2026-10-10T11:30:00Z")
    assert len(active_after) == 0


def test_update_two_area_alert_deactivates_both_polygons():
    """Verify Update referencing base identifier deactivates all multi-area polygons and activates replacement."""
    a1 = _make_alert("alt_multi#1", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z")
    a2 = _make_alert("alt_multi#2", "2026-10-10T10:00:00Z", "2026-10-10T18:00:00Z")
    update = _make_alert("alt_update", "2026-10-10T12:00:00Z", "2026-10-10T20:00:00Z", supersedes="alt_multi")

    alerts = [a1, a2, update]
    active = get_active_alerts(alerts, "2026-10-10T12:30:00Z")
    assert len(active) == 1
    assert active[0].id == "alt_update"


def test_cap_two_reference_cancel_deactivates_both():
    """Verify a Cancel CAP XML containing two references deactivates both referenced alerts."""
    from backend.app.ingest.cap import parse_cap_xml

    orig1 = _make_alert("REF-01", "2026-10-10T08:00:00Z", "2026-10-10T18:00:00Z")
    orig2 = _make_alert("REF-02", "2026-10-10T08:30:00Z", "2026-10-10T18:00:00Z")

    xml_cancel_multi = """<?xml version="1.0" encoding="UTF-8"?>
    <alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>CAP-CANCEL-MULTI</identifier>
      <sender>State Disaster Authority (demo)</sender>
      <sent>2026-10-10T10:00:00+00:00</sent>
      <status>Actual</status>
      <msgType>Cancel</msgType>
      <references>DEMO-AUTH,REF-01,2026-10-10T08:00:00+00:00 DEMO-AUTH,REF-02,2026-10-10T08:30:00+00:00</references>
      <info>
        <category>Met</category>
        <event>Multi-Alert Cancellation</event>
        <area>
          <polygon>12.97,80.21 12.98,80.21 12.98,80.22 12.97,80.21</polygon>
        </area>
      </info>
    </alert>"""

    cancel_records = parse_cap_xml(xml_cancel_multi)
    assert len(cancel_records) == 2
    assert any(c.supersedes == "REF-01" for c in cancel_records)
    assert any(c.supersedes == "REF-02" for c in cancel_records)
    assert any(c.id == "CAP-CANCEL-MULTI~ref2" for c in cancel_records)

    all_alerts = [orig1, orig2] + cancel_records
    active = get_active_alerts(all_alerts, "2026-10-10T10:30:00Z")
    assert len(active) == 0
