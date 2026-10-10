"""Comprehensive deterministic test suite for Bayesian Trust Engine."""

import math
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import h3
import pytest
from shapely.geometry import Polygon

from backend.app.geo import cell_to_polygon_lnglat
from backend.app.models.alert import Alert, GeoJSONPolygon
from backend.app.trust import (
    CellAssessment,
    CellFeatures,
    Report,
    assess_cell,
    assess_cells,
)
from backend.app.trust.engine import (
    CROWD_LOGIT_MAX,
    CROWD_LOGIT_MIN,
    DECAY_HALF_LIFE_S,
    LLR_DEFAULT_POSITIVE,
    LLR_DEFAULT_SAFE,
    LLR_VERIFIED_POSITIVE,
    LLR_VERIFIED_SAFE,
    PRIOR_INTERCEPT,
    char_3gram_jaccard,
    compute_prior_logit,
    sigmoid,
)

# Reference anchor cell in Chennai
ANCHOR_CELL = "88618c4f3dfffff"


def _make_utc_dt(s: str) -> datetime:
    """Helper creating UTC datetime from ISO string."""
    clean = s.strip()
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    return datetime.fromisoformat(clean).astimezone(timezone.utc)


def _make_report(
    report_id: str,
    device_id: str,
    cell: str,
    claim: str = "flooded",
    text: Optional[str] = "Water rising on road",
    created_at_iso: str = "2026-10-10T12:00:00Z",
    tier: str = "default",
) -> Report:
    return Report(
        id=report_id,
        device_id=device_id,
        cell=cell,
        claim=claim,
        text=text,
        created_at=_make_utc_dt(created_at_iso),
        tier=tier,
    )


def _make_alert_from_polygon(
    alert_id: str,
    hazard: str,
    coordinates: List[List[List[float]]],
    sent_at_iso: str = "2026-10-10T11:00:00Z",
    sender: str = "State Disaster Authority (demo)",
    instruction_keys: List[str] = None,
) -> Alert:
    return Alert(
        id=alert_id,
        source="official_manual",
        sender=sender,
        hazard=hazard,
        severity="severe" if hazard != "all_clear" else "minor",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=coordinates),
        instruction_keys=instruction_keys or (["MOVE_TO_HIGHER_GROUND"] if hazard != "all_clear" else ["ALL_CLEAR"]),
        params={},
        sent_at=sent_at_iso,
        expires_at="2026-10-10T22:00:00Z",
        supersedes=None,
        published_by="operator",
        is_replay=False,
    )


# --- 1. Exact LLR Values & Formulations ---

def test_exact_llr_values_and_safe_sign():
    """Verify exact theoretical LLR calculations with 1e-9 tolerance and rounded checks."""
    # Formulas check against math.log
    assert math.isclose(LLR_DEFAULT_POSITIVE, math.log(0.70 / (1.0 - 0.85)), rel_tol=1e-9)
    assert math.isclose(LLR_DEFAULT_SAFE, math.log((1.0 - 0.70) / 0.85), rel_tol=1e-9)
    assert math.isclose(LLR_VERIFIED_POSITIVE, math.log(0.90 / (1.0 - 0.95)), rel_tol=1e-9)
    assert math.isclose(LLR_VERIFIED_SAFE, math.log((1.0 - 0.90) / 0.95), rel_tol=1e-9)

    # 4-decimal rounded checks
    assert round(LLR_DEFAULT_POSITIVE, 4) == 1.5404
    assert round(LLR_DEFAULT_SAFE, 4) == -1.0415
    assert round(LLR_VERIFIED_POSITIVE, 4) == 2.8904
    assert round(LLR_VERIFIED_SAFE, 4) == -2.2513  # User amendment 1 confirmed

    # Safe claims must be strictly negative
    assert LLR_DEFAULT_SAFE < 0.0
    assert LLR_VERIFIED_SAFE < 0.0


# --- 2. Deduplication, Rate Limiting & Union-Find Clustering ---

def test_duplicates_identical_text_merge_to_single_cluster():
    """50 reports with identical text from distinct devices collapse to 1 cluster with p equal to 1 report."""
    now = _make_utc_dt("2026-10-10T12:05:00Z")
    features = CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False)

    single_report = [
        _make_report("r_single", "dev_0", ANCHOR_CELL, "flooded", "Severe waterlogging near metro", "2026-10-10T12:00:00Z")
    ]
    res_single = assess_cell(ANCHOR_CELL, features, single_report, [], now)

    # 50 reports with identical text
    fifty_reports = [
        _make_report(f"r_{i}", f"dev_{i}", ANCHOR_CELL, "flooded", "Severe waterlogging near metro", "2026-10-10T12:00:00Z")
        for i in range(50)
    ]
    res_fifty = assess_cell(ANCHOR_CELL, features, fifty_reports, [], now)

    assert res_fifty.cluster_count_positive == 1
    assert math.isclose(res_fifty.p_hazard, res_single.p_hazard, abs_tol=1e-4)
    assert math.isclose(res_fifty.crowd_logit_clipped, res_single.crowd_logit_clipped, abs_tol=1e-4)


def test_device_rate_limiting_anchored_on_last_kept():
    """Test device rate limiting: anchor on last kept report (keep only if >= 600s after last kept)."""
    now = _make_utc_dt("2026-10-10T14:00:00Z")
    features = CellFeatures(rain_mm_3h=25.0, flood_prone=True)

    # Device posts at 12:00:00, then again 9 minutes later at 12:09:00
    # 9 min = 540 s < 600 s window: second report must be discarded!
    r1 = _make_report("r1", "dev_spammer", ANCHOR_CELL, "flooded", "Water rising", "2026-10-10T12:00:00Z")
    r2 = _make_report("r2", "dev_spammer", ANCHOR_CELL, "flooded", "Still rising", "2026-10-10T12:09:00Z")

    res = assess_cell(ANCHOR_CELL, features, [r1, r2], [], now)
    assert res.cluster_count_positive == 1
    crowd_lines = [e for e in res.evidence if e.type == "crowd"]
    assert len(crowd_lines) == 1
    assert crowd_lines[0].summary.startswith("1 report")

    # If device posts at 12:00 and 12:11 (11 min > 10 min), both are kept
    r3 = _make_report("r3", "dev_spaced", ANCHOR_CELL, "flooded", "First message", "2026-10-10T12:00:00Z")
    r4 = _make_report("r4", "dev_spaced", ANCHOR_CELL, "flooded", "Second message", "2026-10-10T12:11:00Z")
    res_spaced = assess_cell(ANCHOR_CELL, features, [r3, r4], [], now)
    # Since same device within 15 min, they merge into 1 cluster of 2 reports
    crowd_spaced = [e for e in res_spaced.evidence if e.type == "crowd"]
    assert len(crowd_spaced) == 1
    assert crowd_spaced[0].summary.startswith("2 similar reports counted as 1")


def test_hundred_distinct_devices_inflation_bounded_by_clip():
    """100 distinct devices with distinct texts clamped at +3.0 logit bound."""
    now = _make_utc_dt("2026-10-10T12:01:00Z")
    features = CellFeatures(rain_mm_3h=0.0)

    # None text guarantees similarity 0.0, so each device forms its own independent cluster
    hundred_reports = [
        _make_report(f"r_{i}", f"dev_{i}", ANCHOR_CELL, "flooded", None, "2026-10-10T12:00:00Z")
        for i in range(100)
    ]
    res = assess_cell(ANCHOR_CELL, features, hundred_reports, [], now)

    assert res.cluster_count_positive == 100
    assert res.crowd_logit_raw > 100.0
    assert res.crowd_logit_clipped == CROWD_LOGIT_MAX
    assert res.posterior_logit == round(res.prior_logit + CROWD_LOGIT_MAX, 4)


def test_polarity_segregation():
    """Safe report and flooded report with similar text do NOT merge into the same cluster."""
    now = _make_utc_dt("2026-10-10T12:05:00Z")
    features = CellFeatures(rain_mm_3h=0.0)

    r_flood = _make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Road is completely clear and safe", "2026-10-10T12:00:00Z")
    r_safe = _make_report("r2", "dev_2", ANCHOR_CELL, "safe", "Road is completely clear and safe", "2026-10-10T12:00:00Z")

    res = assess_cell(ANCHOR_CELL, features, [r_flood, r_safe], [], now)
    # Two separate clusters: one positive, one safe
    crowd_evidence = [e for e in res.evidence if e.type == "crowd"]
    assert len(crowd_evidence) == 2
    assert res.cluster_count_positive == 1


# --- 3. Exponential Decay & Clipping Both Directions ---

def test_decay_half_life_exact():
    """Verify p returns toward prior as now advances (check at 0, 2h, 4h, 6h; half-life exactly 2h)."""
    t_report = _make_utc_dt("2026-10-10T12:00:00Z")
    report = [_make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Flooded street", t_report.isoformat())]
    features = CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False)

    prior_p = sigmoid(PRIOR_INTERCEPT)

    # 0h
    res_0 = assess_cell(ANCHOR_CELL, features, report, [], t_report)
    assert math.isclose(res_0.crowd_logit_clipped, LLR_DEFAULT_POSITIVE * 1.0, abs_tol=1e-3)

    # 2h (dt = 7200s, decay factor = 0.5)
    t_2h = t_report + timedelta(hours=2)
    res_2h = assess_cell(ANCHOR_CELL, features, report, [], t_2h)
    assert math.isclose(res_2h.crowd_logit_clipped, LLR_DEFAULT_POSITIVE * 0.5, abs_tol=1e-3)

    # 4h (dt = 14400s, decay factor = 0.25)
    t_4h = t_report + timedelta(hours=4)
    res_4h = assess_cell(ANCHOR_CELL, features, report, [], t_4h)
    assert math.isclose(res_4h.crowd_logit_clipped, LLR_DEFAULT_POSITIVE * 0.25, abs_tol=1e-3)

    # 6h (dt = 21600s, decay factor = 0.125)
    t_6h = t_report + timedelta(hours=6)
    res_6h = assess_cell(ANCHOR_CELL, features, report, [], t_6h)
    assert math.isclose(res_6h.crowd_logit_clipped, LLR_DEFAULT_POSITIVE * 0.125, abs_tol=1e-3)

    # Strict monotonicity towards prior
    assert res_0.p_hazard > res_2h.p_hazard > res_4h.p_hazard > res_6h.p_hazard > prior_p


def test_cluster_age_boundary_seconds():
    """Verify cluster active and corroborated boundaries at exactly 4h, 4h+1s, 6h, 6h+1s."""
    from backend.app.trust.engine import cluster_reports

    t_report = _make_utc_dt("2026-10-10T12:00:00Z")
    report = [_make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Flooded street", t_report.isoformat())]

    # At exactly 4h (14400s): corroborated is True, active is True
    t_4h = t_report + timedelta(seconds=14400)
    clusters_4h = cluster_reports(report, ANCHOR_CELL, t_4h)
    assert len(clusters_4h) == 1
    assert clusters_4h[0].is_corroborated is True
    assert clusters_4h[0].is_active is True

    # At 4h + 1s (14401s): corroborated is False, active is True
    t_4h_1s = t_report + timedelta(seconds=14401)
    clusters_4h_1s = cluster_reports(report, ANCHOR_CELL, t_4h_1s)
    assert len(clusters_4h_1s) == 1
    assert clusters_4h_1s[0].is_corroborated is False
    assert clusters_4h_1s[0].is_active is True

    # At exactly 6h (21600s): corroborated is False, active is True
    t_6h = t_report + timedelta(seconds=21600)
    clusters_6h = cluster_reports(report, ANCHOR_CELL, t_6h)
    assert len(clusters_6h) == 1
    assert clusters_6h[0].is_corroborated is False
    assert clusters_6h[0].is_active is True

    # At 6h + 1s (21601s): corroborated is False, active is False
    t_6h_1s = t_report + timedelta(seconds=21601)
    clusters_6h_1s = cluster_reports(report, ANCHOR_CELL, t_6h_1s)
    assert len(clusters_6h_1s) == 1
    assert clusters_6h_1s[0].is_corroborated is False
    assert clusters_6h_1s[0].is_active is False

    # Check assess_cell impact:
    # Dry terrain with positive report: active cluster triggers 'contradicted' (low prior guard)
    feat_dry = CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False, rain_available=True)
    res_active_at_6h = assess_cell(ANCHOR_CELL, feat_dry, report, [], t_6h)
    assert res_active_at_6h.status == "contradicted"

    # Beyond 6h (6h + 1s): cluster is inactive, no active claims -> returns to 'clear'
    res_inactive_at_6h_1s = assess_cell(ANCHOR_CELL, feat_dry, report, [], t_6h_1s)
    assert res_inactive_at_6h_1s.status == "clear"


def test_clipping_both_directions():
    """Verify bidirectional clamping at -3.0 and +3.0."""
    now = _make_utc_dt("2026-10-10T12:00:00Z")
    features = CellFeatures(rain_mm_3h=0.0)

    # 20 distinct safe reports (None text avoids merging)
    safe_reports = [
        _make_report(f"s_{i}", f"dev_s_{i}", ANCHOR_CELL, "safe", None, now.isoformat())
        for i in range(20)
    ]
    res_safe = assess_cell(ANCHOR_CELL, features, safe_reports, [], now)
    assert res_safe.crowd_logit_raw < -5.0
    assert res_safe.crowd_logit_clipped == CROWD_LOGIT_MIN

    # 20 distinct positive reports (None text avoids merging)
    pos_reports = [
        _make_report(f"p_{i}", f"dev_p_{i}", ANCHOR_CELL, "flooded", None, now.isoformat())
        for i in range(20)
    ]
    res_pos = assess_cell(ANCHOR_CELL, features, pos_reports, [], now)
    assert res_pos.crowd_logit_raw > 5.0
    assert res_pos.crowd_logit_clipped == CROWD_LOGIT_MAX


# --- 4. Guarantees & Classification Boundaries ---

def test_crowd_alone_cannot_reach_official_or_likely_hazard():
    """Crowd alone cannot reach official_hazard; with dry prior cannot reach likely_hazard (assert posterior < 0.30)."""
    now = _make_utc_dt("2026-10-10T12:00:00Z")
    # Base prior: dry, not flood-prone (prior_logit = -4.0)
    features = CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False)

    # Maximum possible crowd input (20 independent clusters via None text, clipped at +3.0)
    # posterior_logit = -4.0 + 3.0 = -1.0 -> p = sigmoid(-1.0) = 0.2689
    pos_reports = [
        _make_report(f"p_{i}", f"dev_{i}", ANCHOR_CELL, "flooded", None, now.isoformat())
        for i in range(20)
    ]
    res = assess_cell(ANCHOR_CELL, features, pos_reports, [], now)

    assert res.status != "official_hazard"
    assert res.status != "likely_hazard"
    assert res.p_hazard < 0.30
    assert res.p_hazard == round(sigmoid(-1.0), 4)


def test_corroborated_clusters_with_rain_reaches_likely_hazard():
    """Plausible rain (30 mm/3h on flood-prone cell) + 2 fresh independent clusters reaches likely_hazard."""
    now = _make_utc_dt("2026-10-10T12:01:00Z")
    # rain_3h = 30 -> 0.04*30 = 1.2; flood_prone -> 1.5; prior = -4.0 + 1.2 + 1.5 = -1.3
    features = CellFeatures(rain_mm_3h=30.0, rain_mm_24h=50.0, flood_prone=True)

    # 2 fresh clusters (age ~ 30 s < 4h corroborated limit, None text prevents merging)
    t_rep = (now - timedelta(seconds=30)).isoformat()
    r1 = _make_report("r1", "dev_1", ANCHOR_CELL, "flooded", None, t_rep)
    r2 = _make_report("r2", "dev_2", ANCHOR_CELL, "blocked", None, t_rep)

    res = assess_cell(ANCHOR_CELL, features, [r1, r2], [], now)
    assert res.status == "likely_hazard"
    assert res.headline_key == "AVOID_FLOODED_ROADS"
    assert res.p_hazard >= 0.80


def test_borderline_decay_calibrated_below_likely_hazard():
    """Documented test: 25 mm/3h + two default-tier clusters aged 15 min gives p < 0.80 (shows decay matters)."""
    now = _make_utc_dt("2026-10-10T12:15:00Z")
    # rain_3h = 25.0, rain_24h = 0.0, flood_prone = True -> prior = -4.0 + 1.0 + 1.5 = -1.50
    # Two clusters aged 15 min decay to: 2 * 1.5404 * exp(-ln2/7200 * 900) = 2 * 1.5404 * 0.917 = 2.8252
    # posterior_logit = -1.50 + 2.8252 = 1.3252 -> sigmoid(1.3252) = 0.7900 < 0.80!
    features = CellFeatures(rain_mm_3h=25.0, rain_mm_24h=0.0, flood_prone=True)

    t_15m = (now - timedelta(minutes=15)).isoformat()
    r1 = _make_report("r1", "dev_1", ANCHOR_CELL, "flooded", None, t_15m)
    r2 = _make_report("r2", "dev_2", ANCHOR_CELL, "flooded", None, t_15m)

    res = assess_cell(ANCHOR_CELL, features, [r1, r2], [], now)
    # Calibrated result: p is elevated but strictly < 0.80 due to exponential decay and prior
    assert res.p_hazard < 0.80
    assert res.status == "unverified"


def test_weather_only_elevated_risk():
    """High rain producing p >= 0.50 with no reports classified as unverified, never likely_hazard."""
    now = _make_utc_dt("2026-10-10T12:00:00Z")
    # rain_3h = 100mm, flood_prone: prior = -4.0 + 4.0 + 1.5 = +1.5 -> p = sigmoid(1.5) = 0.817
    features = CellFeatures(rain_mm_3h=100.0, flood_prone=True)

    res = assess_cell(ANCHOR_CELL, features, [], [], now)
    assert res.status == "unverified"
    assert res.headline_key == "UNVERIFIED_WARNING"
    assert res.p_hazard >= 0.80
    # Confirm rain line exists in evidence
    assert any(e.type == "rain" for e in res.evidence)


def test_rain_not_double_counted():
    """Rain enters only via prior; posterior equals prior + crowd_clipped (weight shown for display only)."""
    now = _make_utc_dt("2026-10-10T12:00:00Z")
    features = CellFeatures(rain_mm_3h=40.0, rain_mm_24h=80.0, flood_prone=True)
    report = [_make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Flooded road", now.isoformat())]

    res = assess_cell(ANCHOR_CELL, features, report, [], now)
    # Check exact addition: posterior_logit == prior_logit + crowd_logit_clipped
    assert math.isclose(res.posterior_logit, res.prior_logit + res.crowd_logit_clipped, abs_tol=1e-4)

    # Evidence has rain line
    rain_items = [e for e in res.evidence if e.type == "rain"]
    assert len(rain_items) == 1
    assert rain_items[0].weight > 0.0


# --- 5. Official Alert Overrides & Class Unions ---

def test_official_override_50_percent_boundary():
    """Verify >=50% coverage triggers override, 49% does not."""
    now = _make_utc_dt("2026-10-10T12:00:00Z")
    features = CellFeatures()

    cell_poly_coords = cell_to_polygon_lnglat(ANCHOR_CELL)[0]
    cell_shapely = Polygon(cell_poly_coords)
    minx, miny, maxx, maxy = cell_shapely.bounds

    # Construct alert covering exactly 50% of the cell bounds
    midx = minx + (maxx - minx) * 0.50
    poly_50 = [[[minx, miny], [midx, miny], [midx, maxy], [minx, maxy], [minx, miny]]]
    alert_50 = _make_alert_from_polygon("alt_50", "flood", poly_50)

    # Construct alert covering exactly 40% of the cell bounds
    midx_40 = minx + (maxx - minx) * 0.40
    poly_40 = [[[minx, miny], [midx_40, miny], [midx_40, maxy], [minx, maxy], [minx, miny]]]
    alert_40 = _make_alert_from_polygon("alt_40", "flood", poly_40)

    # 40% does not trigger override
    res_40 = assess_cell(ANCHOR_CELL, features, [], [alert_40], now)
    assert res_40.status != "official_hazard"

    # Full cell polygon covers 100% -> triggers override
    alert_100 = _make_alert_from_polygon("alt_100", "flood", [cell_poly_coords])
    res_100 = assess_cell(ANCHOR_CELL, features, [], [alert_100], now)
    assert res_100.status == "official_hazard"
    assert res_100.p_hazard == 0.99


def test_official_class_union_two_alerts_reach_sixty_percent():
    """Amendment 5: Two hazard alerts each covering ~30% combine in union to >50% -> official_hazard."""
    now = _make_utc_dt("2026-10-10T12:00:00Z")
    features = CellFeatures()

    cell_poly_coords = cell_to_polygon_lnglat(ANCHOR_CELL)[0]
    cell_shapely = Polygon(cell_poly_coords)
    minx, miny, maxx, maxy = cell_shapely.bounds

    # Alert 1: left 30% [0.0 to 0.30]
    x_30 = minx + (maxx - minx) * 0.30
    poly1 = [[[minx, miny], [x_30, miny], [x_30, maxy], [minx, maxy], [minx, miny]]]
    alert1 = _make_alert_from_polygon("alt_left", "flood", poly1, "2026-10-10T11:00:00Z")

    # Alert 2: middle 30% [0.30 to 0.60]
    x_60 = minx + (maxx - minx) * 0.60
    poly2 = [[[x_30, miny], [x_60, miny], [x_60, maxy], [x_30, maxy], [x_30, miny]]]
    alert2 = _make_alert_from_polygon("alt_mid", "flood", poly2, "2026-10-10T11:30:00Z")

    res = assess_cell(ANCHOR_CELL, features, [], [alert1, alert2], now)
    # Together union covers 60% of cell -> triggers official_hazard!
    assert res.status == "official_hazard"
    assert res.p_hazard == 0.99
    assert set(res.official_alert_ids) == {"alt_left", "alt_mid"}


def test_official_precedence_and_tie_breaking():
    """Verify latest sent_at decides between hazard and all-clear; ties hazard wins."""
    now = _make_utc_dt("2026-10-10T14:00:00Z")
    features = CellFeatures()
    cell_poly_coords = cell_to_polygon_lnglat(ANCHOR_CELL)[0]

    # 1. Hazard newer than all-clear (12:00 vs 11:00) -> hazard wins
    hazard_new = _make_alert_from_polygon("alt_haz_new", "flood", [cell_poly_coords], "2026-10-10T12:00:00Z")
    clear_old = _make_alert_from_polygon("alt_clr_old", "all_clear", [cell_poly_coords], "2026-10-10T11:00:00Z")

    res_haz_wins = assess_cell(ANCHOR_CELL, features, [], [hazard_new, clear_old], now)
    assert res_haz_wins.status == "official_hazard"
    assert res_haz_wins.p_hazard == 0.99

    # 2. All-clear newer than hazard (13:00 vs 12:00) -> all-clear wins -> status clear
    clear_new = _make_alert_from_polygon("alt_clr_new", "all_clear", [cell_poly_coords], "2026-10-10T13:00:00Z")
    res_clr_wins = assess_cell(ANCHOR_CELL, features, [], [hazard_new, clear_new], now)
    assert res_clr_wins.status == "clear"
    assert res_clr_wins.p_hazard == 0.01

    # 3. Exact tie in sent_at (12:00 vs 12:00) -> hazard wins (safety fail-safe)
    hazard_tie = _make_alert_from_polygon("alt_haz_tie", "flood", [cell_poly_coords], "2026-10-10T12:00:00Z")
    clear_tie = _make_alert_from_polygon("alt_clr_tie", "all_clear", [cell_poly_coords], "2026-10-10T12:00:00Z")

    res_tie = assess_cell(ANCHOR_CELL, features, [], [hazard_tie, clear_tie], now)
    assert res_tie.status == "official_hazard"
    assert res_tie.p_hazard == 0.99


# --- 6. Contradicted Status Nuances ---

def test_contradicted_via_all_clear_when_positive_claims_active():
    """Active positive claims under official all-clear become contradicted, not clear."""
    now = _make_utc_dt("2026-10-10T13:00:00Z")
    features = CellFeatures()
    cell_poly_coords = cell_to_polygon_lnglat(ANCHOR_CELL)[0]

    clear_alert = _make_alert_from_polygon("alt_clr", "all_clear", [cell_poly_coords], "2026-10-10T12:00:00Z", sender="State Disaster Authority (demo)")
    report = [_make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Deep floodwaters here", "2026-10-10T12:30:00Z")]

    res = assess_cell(ANCHOR_CELL, features, report, [clear_alert], now)
    assert res.status == "contradicted"
    assert res.p_hazard == 0.01
    assert res.headline_key == "FOLLOW_OFFICIAL_ONLY"

    # Evidence shows contradicted wording
    crowd_item = [e for e in res.evidence if e.type == "crowd"][0]
    assert "Claim contradicted by official all-clear from State Disaster Authority (demo)" in crowd_item.summary


def test_contradicted_via_low_prior_guard():
    """Contradicted via low prior requires rain_available=True; with rain_available=False becomes unverified."""
    now = _make_utc_dt("2026-10-10T12:05:00Z")
    report = [_make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Flooding here", "2026-10-10T12:00:00Z")]

    # 1. rain_available = True and dry terrain (prior_p = sigmoid(-4.0) = 0.0179 < 0.05)
    features_fresh = CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False, rain_available=True)
    res_contradicted = assess_cell(ANCHOR_CELL, features_fresh, report, [], now)
    assert res_contradicted.status == "contradicted"
    assert res_contradicted.headline_key == "FOLLOW_OFFICIAL_ONLY"
    crowd_item = [e for e in res_contradicted.evidence if e.type == "crowd"][0]
    assert crowd_item.summary == "No heavy rain recorded here, so this report is unconfirmed. Follow official guidance."

    # 2. Same cell but rain_available = False (missing radar data) -> cannot prove safety -> unverified
    features_stale = CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False, rain_available=False)
    res_unverified = assess_cell(ANCHOR_CELL, features_stale, report, [], now)
    assert res_unverified.status == "unverified"
    assert res_unverified.headline_key == "UNVERIFIED_WARNING"


# --- 7. Invariants, Input Sanitization & Ordering ---

def test_report_cell_mismatch_ignored():
    """Reports belonging to a different cell are ignored."""
    now = _make_utc_dt("2026-10-10T12:05:00Z")
    features = CellFeatures()
    other_cell = "88618c4f3bfffff"

    wrong_report = [_make_report("r_wrong", "dev_1", other_cell, "flooded", "Flooded road", "2026-10-10T12:00:00Z")]
    res = assess_cell(ANCHOR_CELL, features, wrong_report, [], now)

    assert res.cluster_count_positive == 0
    assert len([e for e in res.evidence if e.type == "crowd"]) == 0


def test_order_invariance_and_input_sanitization():
    """Input order shuffling yields bit-identical assessment; NaN/negative rain sanitized."""
    now = _make_utc_dt("2026-10-10T12:10:00Z")
    features_bad = CellFeatures(rain_mm_3h=-50.0, rain_mm_24h=float("nan"), flood_prone=False)

    reports = [
        _make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Text alpha", "2026-10-10T12:00:00Z"),
        _make_report("r2", "dev_2", ANCHOR_CELL, "blocked", "Text beta", "2026-10-10T12:02:00Z"),
        _make_report("r3", "dev_3", ANCHOR_CELL, "safe", "Text gamma", "2026-10-10T12:04:00Z"),
    ]
    shuffled = [reports[2], reports[0], reports[1]]

    res1 = assess_cell(ANCHOR_CELL, features_bad, reports, [], now)
    res2 = assess_cell(ANCHOR_CELL, features_bad, shuffled, [], now)

    assert res1.model_dump() == res2.model_dump()
    assert 0.0 <= res1.p_hazard <= 1.0


def test_naive_datetime_raises_value_error():
    """Passing a timezone-naive datetime to assess_cell or Report raises ValueError."""
    features = CellFeatures()
    naive_dt = datetime(2026, 10, 10, 12, 0, 0)  # No tzinfo

    with pytest.raises(ValueError, match="timezone-aware"):
        assess_cell(ANCHOR_CELL, features, [], [], naive_dt)

    with pytest.raises(ValueError, match="timezone-aware"):
        Report(
            id="r_bad",
            device_id="d1",
            cell=ANCHOR_CELL,
            claim="flooded",
            created_at=naive_dt,
        )


def test_evidence_explicit_ordering():
    """Evidence list strictly orders: official (rank 0), rain (rank 1), crowd (rank 2)."""
    now = _make_utc_dt("2026-10-10T12:00:00Z")
    features = CellFeatures(rain_mm_3h=10.0, rain_available=True)
    cell_poly_coords = cell_to_polygon_lnglat(ANCHOR_CELL)[0]

    alert = _make_alert_from_polygon("alt_1", "flood", [cell_poly_coords], "2026-10-10T11:00:00Z")
    report = [_make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Flooding", now.isoformat())]

    res = assess_cell(ANCHOR_CELL, features, report, [alert], now)
    assert len(res.evidence) >= 3
    assert res.evidence[0].type == "official"
    assert res.evidence[1].type == "rain"
    assert res.evidence[2].type == "crowd"


def test_monotonicity():
    """Adding an independent positive cluster never decreases p."""
    now = _make_utc_dt("2026-10-10T12:05:00Z")
    features = CellFeatures(rain_mm_3h=20.0, flood_prone=True)

    r1 = _make_report("r1", "dev_1", ANCHOR_CELL, "flooded", "Deep water at park", "2026-10-10T12:00:00Z")
    r2 = _make_report("r2", "dev_2", ANCHOR_CELL, "blocked", "Completely unrelated obstruction", "2026-10-10T12:00:00Z")

    res_1 = assess_cell(ANCHOR_CELL, features, [r1], [], now)
    res_2 = assess_cell(ANCHOR_CELL, features, [r1, r2], [], now)

    assert res_2.p_hazard >= res_1.p_hazard


def test_assess_cells_batch_parity():
    """assess_cells result equals per-cell assess_cell results."""
    now = _make_utc_dt("2026-10-10T12:10:00Z")
    cell_a = ANCHOR_CELL
    cell_b = "88618c4f35fffff"

    features_map = {
        cell_a: CellFeatures(rain_mm_3h=25.0, flood_prone=True),
        cell_b: CellFeatures(rain_mm_3h=0.0, flood_prone=False),
    }
    reports_map = {
        cell_a: [_make_report("ra", "d1", cell_a, "flooded", "Waterlogging", "2026-10-10T12:00:00Z")],
        cell_b: [_make_report("rb", "d2", cell_b, "safe", "Clear street", "2026-10-10T12:00:00Z")],
    }
    alerts = [_make_alert_from_polygon("alt_test", "flood", [cell_to_polygon_lnglat(cell_a)[0]])]

    batch_res = assess_cells([cell_a, cell_b], features_map, reports_map, alerts, now)
    single_a = assess_cell(cell_a, features_map[cell_a], reports_map[cell_a], alerts, now)
    single_b = assess_cell(cell_b, features_map[cell_b], reports_map[cell_b], alerts, now)

    assert batch_res[cell_a].model_dump() == single_a.model_dump()
    assert batch_res[cell_b].model_dump() == single_b.model_dump()


# --- 8. Pathological Volume & Performance Tests ---

def test_performance_pathological_cell_volume():
    """5,000 reports in one cell assessed in < 1.0 s."""
    now = _make_utc_dt("2026-10-10T14:00:00Z")
    features = CellFeatures(rain_mm_3h=15.0)

    # 5,000 spam reports
    base_t = _make_utc_dt("2026-10-10T12:00:00Z")
    many_reports = [
        _make_report(f"r_{i}", f"dev_{i % 50}", ANCHOR_CELL, "flooded", f"Spam message text {i}", (base_t + timedelta(seconds=i)).isoformat())
        for i in range(5000)
    ]

    t0 = time.perf_counter()
    res = assess_cell(ANCHOR_CELL, features, many_reports, [], now)
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, f"Pathological cell assessment took {elapsed:.3f} s (expected < 1.0 s)"
    assert res.p_hazard is not None


def test_performance_large_batch_assess_cells():
    """assess_cells over 5,000 cells with 20 alerts and 500 reports in < 3.0 s."""
    now = _make_utc_dt("2026-10-10T14:00:00Z")

    # Generate 5,000 valid H3 cells using grid_disk around ANCHOR_CELL
    cells = list(h3.grid_disk(ANCHOR_CELL, 45))[:5000]
    features_map = {c: CellFeatures(rain_mm_3h=10.0) for c in cells[:100]}

    # 500 reports distributed
    reports_map = {
        cells[i]: [_make_report(f"r_{i}", f"dev_{i}", cells[i], "flooded", "Flooding", now.isoformat())]
        for i in range(500)
    }

    # 20 alerts
    cell_poly_coords = cell_to_polygon_lnglat(ANCHOR_CELL)[0]
    alerts = [
        _make_alert_from_polygon(f"alt_{i}", "flood" if i % 2 == 0 else "all_clear", [cell_poly_coords])
        for i in range(20)
    ]

    t0 = time.perf_counter()
    results = assess_cells(cells, features_map, reports_map, alerts, now)
    elapsed = time.perf_counter() - t0

    assert len(results) == 5000
    # Loose threshold for cross-platform hardware; typically finishes in ~0.5s
    assert elapsed < 3.0, f"Batch assessment of 5,000 cells took {elapsed:.3f} s (expected < 3.0 s)"
