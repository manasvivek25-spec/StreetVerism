"""Comprehensive unit and narrative test suite for StreetVerism Replay Engine."""

import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import h3
import pytest
from shapely.geometry import Point, Polygon

from backend.app.geo import cell_to_polygon_lnglat, cells_in_bbox, latlng_to_cell
from backend.app.models.alert import Alert, GeoJSONPolygon
from backend.app.scenario import (
    REPLAY_DISCLAIMER,
    REPLAY_LABEL,
    ReplayOverlay,
    ScenarioClock,
    features_for_cell,
    load_scenario,
    scenario_inputs_at,
)
from backend.app.scenario.clock import _utc_now
from backend.app.scenario.loader import (
    MAX_LAT,
    MAX_LNG,
    MIN_LAT,
    MIN_LNG,
)
from backend.app.scenario.types import RainKeyframe, Scenario
from backend.app.trust import assess_cell, assess_cells
from backend.app.trust.engine import (
    CROWD_LOGIT_MAX,
    cluster_reports,
    compute_prior_logit,
    sigmoid,
)
from backend.app.trust.types import CellAssessment, CellFeatures, Report

SCENARIO_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "scenarios" / "michaung_replay.json"
SHELTERS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "shelters.json"


@pytest.fixture(scope="module")
def scenario() -> Scenario:
    return load_scenario(SCENARIO_PATH, SHELTERS_PATH)


# --- 1. Load and Validation Errors ---

def test_load_scenario_valid(scenario: Scenario):
    """Verify clean load of reference michaung scenario."""
    assert scenario.name == "Cyclone Michaung Replay"
    assert scenario.label == REPLAY_LABEL
    assert scenario.disclaimer == REPLAY_DISCLAIMER
    assert scenario.is_replay is True
    assert scenario.values_are_approximate is True
    assert scenario.duration_s == 86400
    assert len(scenario.area_groups) == 5
    assert len(scenario.alerts) == 5
    assert len(scenario.reports) == 86
    assert len(scenario.bookmarks) == 5


def test_validation_missing_file():
    with pytest.raises(FileNotFoundError):
        load_scenario("data/scenarios/non_existent.json")


def test_validation_coordinate_out_of_bounds(tmp_path):
    """Reject coordinates outside Chennai bounding box [lat 12.8-13.3, lng 80.1-80.4]."""
    import json
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Invert/corrupt first report latitude
    data["reports"][0]["lat"] = 14.50
    bad_file = tmp_path / "bad_coord.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError, match="Coordinate sanity violation"):
        load_scenario(bad_file, SHELTERS_PATH)


def test_validation_coordinate_order_swapped(tmp_path):
    """Detect lat/lng coordinate order swap (lng in lat range or vice versa)."""
    import json
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Swap lat/lng in group polygon
    data["area_groups"][0]["polygon"]["coordinates"][0][0] = [12.960, 80.205]
    bad_file = tmp_path / "swapped_coord.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError, match="Coordinate sanity violation"):
        load_scenario(bad_file, SHELTERS_PATH)


def test_validation_unsorted_keyframes(tmp_path):
    """Reject keyframes that are not strictly sorted by t_offset_s."""
    import json
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["area_groups"][0]["keyframes"][1]["t_offset_s"] = 0
    bad_file = tmp_path / "unsorted_kf.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError, match="strictly sorted"):
        load_scenario(bad_file, SHELTERS_PATH)


def test_validation_keyframe_offset_out_of_bounds(tmp_path):
    """Reject keyframe offset beyond scenario duration."""
    import json
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["area_groups"][0]["keyframes"][-1]["t_offset_s"] = 999999
    bad_file = tmp_path / "kf_oob.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError, match="out of bounds"):
        load_scenario(bad_file, SHELTERS_PATH)


def test_validation_rain_24h_less_than_3h():
    """Verify Pydantic model rejects rain_mm_24h < rain_mm_3h."""
    with pytest.raises(ValueError, match="greater than or equal to rain_mm_3h"):
        RainKeyframe(t_offset_s=100, rain_mm_3h=50.0, rain_mm_24h=30.0)


def test_validation_unknown_shelter_id(tmp_path):
    """Reject alert referencing shelter ID that does not exist in shelters.json."""
    import json
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["alerts"][2]["params"]["shelter"] = "sh_nonexistent_999"
    bad_file = tmp_path / "bad_shelter.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError, match="unknown shelter ID"):
        load_scenario(bad_file, SHELTERS_PATH)


def test_validation_alert_sent_gte_expires(tmp_path):
    """Reject alert where sent_at >= expires_at."""
    import json
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    data["alerts"][0]["sent_at"] = data["alerts"][0]["expires_at"]
    bad_file = tmp_path / "bad_timing.json"
    with open(bad_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    with pytest.raises(ValueError, match="strictly earlier than expires_at"):
        load_scenario(bad_file, SHELTERS_PATH)


# --- 2. Honesty and Metadata Invariants ---

def test_honesty_rules_and_constants(scenario: Scenario):
    """Verify all honesty metadata and constants."""
    assert REPLAY_LABEL == "Replay: illustrative reconstruction"
    assert REPLAY_DISCLAIMER == "Simulated data based loosely on a past event, not real or official."

    assert scenario.label == REPLAY_LABEL
    assert scenario.disclaimer == REPLAY_DISCLAIMER
    assert scenario.is_replay is True

    # Alerts source and sender
    for alert in scenario.alerts:
        assert alert.source == "replay"
        assert "(replay)" in alert.sender
        assert alert.sender == "State Disaster Authority (replay)"
        assert alert.is_replay is True

    # Shelters demo flag
    import json
    with open(SHELTERS_PATH, "r", encoding="utf-8") as f:
        shelters_data = json.load(f)
    for sh in shelters_data:
        assert sh.get("is_demo") is True
        assert "Demo" in sh["name"]


# --- 3. Seek Invariance ---

def test_seek_invariance(scenario: Scenario):
    """Point-in-time state is a pure function of (scenario, t); past seek history does not matter."""
    t_target = scenario.t0 + timedelta(hours=9, minutes=30)

    # 1. Direct evaluation at target
    inputs_1 = scenario_inputs_at(scenario, t_target)

    # 2. Sequential seek history (forward, backward, forward)
    _ = scenario_inputs_at(scenario, scenario.t0 + timedelta(hours=14))
    _ = scenario_inputs_at(scenario, scenario.t0 + timedelta(hours=2))
    _ = scenario_inputs_at(scenario, scenario.t0 + timedelta(hours=22))
    inputs_2 = scenario_inputs_at(scenario, t_target)

    assert len(inputs_1.alerts) == len(inputs_2.alerts)
    assert [a.id for a in inputs_1.alerts] == [a.id for a in inputs_2.alerts]
    assert len(inputs_1.reports) == len(inputs_2.reports)
    assert [r.id for r in inputs_1.reports] == [r.id for r in inputs_2.reports]

    # Verify features for multiple representative cells
    for group in scenario.area_groups:
        pt = group.representative_point
        cell = latlng_to_cell(pt.lat, pt.lng, 8)
        f1 = inputs_1.features_for_cell(cell)
        f2 = inputs_2.features_for_cell(cell)
        assert f1.rain_mm_3h == f2.rain_mm_3h
        assert f1.rain_mm_24h == f2.rain_mm_24h
        assert f1.flood_prone == f2.flood_prone
        assert f1.rain_available == f2.rain_available


# --- 4. ScenarioClock Mechanics ---

def test_scenario_clock_speeds_and_pausing(scenario: Scenario):
    """Test clock speeds 1, 60, 600, pausing, and time advancement."""
    wall_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)

    def mock_wall():
        return wall_time

    overlay = ReplayOverlay()
    clock = ScenarioClock(scenario, wall_clock=mock_wall, overlay=overlay)

    # Initial state: at t0, paused
    assert clock.sim_time() == scenario.t0
    st = clock.status()
    assert st["paused"] is True
    assert st["is_running"] is False
    assert st["speed"] == 0.0

    # Start at speed 1
    clock.start(speed=1.0)
    assert clock.status()["is_running"] is True
    wall_time += timedelta(seconds=10)
    assert clock.sim_time() == scenario.t0 + timedelta(seconds=10)

    # Change speed to 60
    clock.start(speed=60.0)
    wall_time += timedelta(seconds=5)
    # Elapsed: 10s + 5s * 60 = 310s
    assert clock.sim_time() == scenario.t0 + timedelta(seconds=310)

    # Change speed to 600
    clock.start(speed=600.0)
    wall_time += timedelta(seconds=2)
    # Elapsed: 310s + 2s * 600 = 1510s
    assert clock.sim_time() == scenario.t0 + timedelta(seconds=1510)

    # Pause
    clock.pause()
    assert clock.status()["paused"] is True
    wall_time += timedelta(seconds=100)
    assert clock.sim_time() == scenario.t0 + timedelta(seconds=1510)


def test_scenario_clock_seek_xor_rule(scenario: Scenario):
    """Seek requires exactly one of t or offset_s (XOR rule)."""
    clock = ScenarioClock(scenario)

    # Both provided -> ValueError
    with pytest.raises(ValueError, match="Exactly one"):
        clock.seek(t=scenario.t0, offset_s=100)

    # Neither provided -> ValueError
    with pytest.raises(ValueError, match="Exactly one"):
        clock.seek()

    # Valid t
    res_t = clock.seek(t=scenario.t0 + timedelta(hours=5))
    assert res_t == scenario.t0 + timedelta(hours=5)

    # Valid offset_s
    res_off = clock.seek(offset_s=7200)
    assert res_off == scenario.t0 + timedelta(hours=2)


def test_scenario_clock_clamp_and_finished_restart(scenario: Scenario):
    """Clock clamps to [t0, t_end]; start from finished state restarts at t0."""
    wall_time = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)
    clock = ScenarioClock(scenario, wall_clock=lambda: wall_time)

    # Clamp below t0
    clock.seek(offset_s=-500)
    assert clock.sim_time() == scenario.t0

    # Clamp above t_end
    clock.seek(offset_s=999999)
    assert clock.sim_time() == scenario.t0 + timedelta(seconds=scenario.duration_s)
    assert clock.status()["finished"] is True

    # start() when finished restarts from t0
    clock.start(speed=1.0)
    assert clock.sim_time() == scenario.t0
    assert clock.status()["finished"] is False


def test_scenario_clock_overlay_clearing_rules(scenario: Scenario):
    """Seek never clears overlay; start and reset clear overlay."""
    overlay = ReplayOverlay()
    clock = ScenarioClock(scenario, overlay=overlay)

    rep = Report(
        id="dyn_1",
        device_id="dyn_dev_1",
        cell="88618c4f1dfffff",
        claim="flooded",
        created_at=scenario.t0 + timedelta(hours=5),
    )
    overlay.add_report(rep)
    assert len(overlay) == 1

    # Seek does NOT clear overlay
    clock.seek(offset_s=3600)
    assert len(overlay) == 1

    # Reset clears overlay
    clock.reset()
    assert len(overlay) == 0

    # Add again and verify start clears overlay
    overlay.add_report(rep)
    assert len(overlay) == 1
    clock.start(speed=10.0)
    assert len(overlay) == 0


def test_scenario_clock_invalid_speed(scenario: Scenario):
    clock = ScenarioClock(scenario)
    with pytest.raises(ValueError, match="Speed must be within"):
        clock.start(speed=-1.0)
    with pytest.raises(ValueError, match="Speed must be within"):
        clock.start(speed=3601.0)


# --- 5. Narrative Tests with Real Trust Engine ---

def test_narrative_group_2_early_warning_and_upgrade(scenario: Scenario):
    """Group 2 Adyar: reaches likely_hazard at ~7h30 before official alert at 9h00, upgrades to official_hazard."""
    adyar_cell = latlng_to_cell(13.015, 80.225, 8)

    # 1. At 6h50: before reports, heavy rain only -> clear or unverified
    t_6h50 = scenario.t0 + timedelta(hours=6, minutes=50)
    in_6h50 = scenario_inputs_at(scenario, t_6h50)
    f_6h50 = in_6h50.features_for_cell(adyar_cell)
    res_6h50 = assess_cell(adyar_cell, f_6h50, in_6h50.reports, in_6h50.alerts, t_6h50)
    assert res_6h50.status != "likely_hazard"
    assert res_6h50.status != "official_hazard"

    # 2. At 7h30: 2 fresh independent reports spaced 25 min arrive in heavy rain flood-prone cell -> likely_hazard!
    t_7h30 = scenario.t0 + timedelta(hours=7, minutes=30)
    in_7h30 = scenario_inputs_at(scenario, t_7h30)
    f_7h30 = in_7h30.features_for_cell(adyar_cell)
    res_7h30 = assess_cell(adyar_cell, f_7h30, in_7h30.reports, in_7h30.alerts, t_7h30)
    assert res_7h30.status == "likely_hazard"
    assert res_7h30.headline_key == "AVOID_FLOODED_ROADS"
    assert res_7h30.p_hazard >= 0.80

    # 3. At 8h59: just before official alert arrives, still likely_hazard
    t_8h59 = scenario.t0 + timedelta(hours=8, minutes=59)
    in_8h59 = scenario_inputs_at(scenario, t_8h59)
    f_8h59 = in_8h59.features_for_cell(adyar_cell)
    res_8h59 = assess_cell(adyar_cell, f_8h59, in_8h59.reports, in_8h59.alerts, t_8h59)
    assert res_8h59.status == "likely_hazard"

    # 4. At 9h01: official extreme flood alert becomes active -> upgraded to official_hazard!
    t_9h01 = scenario.t0 + timedelta(hours=9, minutes=1)
    in_9h01 = scenario_inputs_at(scenario, t_9h01)
    f_9h01 = in_9h01.features_for_cell(adyar_cell)
    res_9h01 = assess_cell(adyar_cell, f_9h01, in_9h01.reports, in_9h01.alerts, t_9h01)
    assert res_9h01.status == "official_hazard"
    assert res_9h01.p_hazard == 0.99
    assert res_9h01.headline_key == "MOVE_TO_HIGHER_GROUND"


def test_narrative_rumor_zone_progression_and_aging(scenario: Scenario):
    """Rumor Zone: collapses to unverified across all 3 waves, contradicted after all-clear, clear after aging out."""
    rumor_cell = latlng_to_cell(13.055, 80.225, 8)

    # 1. At 8h30 (wave 1: 40 duplicate reports collapse to 1 cluster): unverified, never likely_hazard
    t_8h30 = scenario.t0 + timedelta(hours=8, minutes=30)
    in_8h30 = scenario_inputs_at(scenario, t_8h30)
    f_8h30 = in_8h30.features_for_cell(rumor_cell)
    res_8h30 = assess_cell(rumor_cell, f_8h30, in_8h30.reports, in_8h30.alerts, t_8h30)
    assert res_8h30.status == "unverified"
    assert res_8h30.headline_key == "UNVERIFIED_WARNING"

    # 2. At 9h30 (wave 2): unverified, never likely_hazard
    t_9h30 = scenario.t0 + timedelta(hours=9, minutes=30)
    in_9h30 = scenario_inputs_at(scenario, t_9h30)
    f_9h30 = in_9h30.features_for_cell(rumor_cell)
    res_9h30 = assess_cell(rumor_cell, f_9h30, in_9h30.reports, in_9h30.alerts, t_9h30)
    assert res_9h30.status == "unverified"
    assert res_9h30.p_hazard < 0.80

    # 3. At 10h45 (wave 3): unverified, never likely_hazard
    t_10h45 = scenario.t0 + timedelta(hours=10, minutes=45)
    in_10h45 = scenario_inputs_at(scenario, t_10h45)
    f_10h45 = in_10h45.features_for_cell(rumor_cell)
    res_10h45 = assess_cell(rumor_cell, f_10h45, in_10h45.reports, in_10h45.alerts, t_10h45)
    assert res_10h45.status == "unverified"
    assert res_10h45.p_hazard < 0.80

    # 4. At 11h30 (after official all-clear at 11h00): contradicted
    t_11h30 = scenario.t0 + timedelta(hours=11, minutes=30)
    in_11h30 = scenario_inputs_at(scenario, t_11h30)
    f_11h30 = in_11h30.features_for_cell(rumor_cell)
    res_11h30 = assess_cell(rumor_cell, f_11h30, in_11h30.reports, in_11h30.alerts, t_11h30)
    assert res_11h30.status == "contradicted"
    assert res_11h30.headline_key == "FOLLOW_OFFICIAL_ONLY"
    assert res_11h30.p_hazard == 0.01

    # 5. At 16h29 (just before wave 3 claims age out): still contradicted
    t_16h29 = scenario.t0 + timedelta(hours=16, minutes=29)
    in_16h29 = scenario_inputs_at(scenario, t_16h29)
    f_16h29 = in_16h29.features_for_cell(rumor_cell)
    res_16h29 = assess_cell(rumor_cell, f_16h29, in_16h29.reports, in_16h29.alerts, t_16h29)
    assert res_16h29.status == "contradicted"

    # 6. At 17h00 (claims aged out > 6h): clear!
    t_17h00 = scenario.t0 + timedelta(hours=17, minutes=0)
    in_17h00 = scenario_inputs_at(scenario, t_17h00)
    f_17h00 = in_17h00.features_for_cell(rumor_cell)
    res_17h00 = assess_cell(rumor_cell, f_17h00, in_17h00.reports, in_17h00.alerts, t_17h00)
    assert res_17h00.status == "clear"
    assert res_17h00.headline_key == "ALL_CLEAR"


def test_narrative_calm_zone_clear_throughout(scenario: Scenario):
    """Calm zone stays clear across all 24 simulated hours."""
    calm_cell = latlng_to_cell(13.100, 80.160, 8)

    for h in range(25):
        t_eval = scenario.t0 + timedelta(hours=h)
        inputs = scenario_inputs_at(scenario, t_eval)
        feat = inputs.features_for_cell(calm_cell)
        res = assess_cell(calm_cell, feat, inputs.reports, inputs.alerts, t_eval)
        assert res.status == "clear", f"Calm cell failed at hour {h}: got {res.status}"
        assert res.p_hazard < 0.50


def test_no_cell_official_hazard_without_active_alert(scenario: Scenario):
    """Independently verify with Shapely that no cell is official_hazard without >=50% coverage by active official hazard alert."""
    test_times = [
        scenario.t0 + timedelta(hours=0),
        scenario.t0 + timedelta(hours=4),
        scenario.t0 + timedelta(hours=7),
        scenario.t0 + timedelta(hours=10),
        scenario.t0 + timedelta(hours=15),
    ]

    for t in test_times:
        inputs = scenario_inputs_at(scenario, t)
        hazard_alerts = [a for a in inputs.alerts if a.hazard != "all_clear"]

        for group in scenario.area_groups:
            pt = group.representative_point
            cell = latlng_to_cell(pt.lat, pt.lng, 8)
            feat = inputs.features_for_cell(cell)
            res = assess_cell(cell, feat, inputs.reports, inputs.alerts, t)

            # Independent coverage calculation with Shapely
            boundary = h3.cell_to_boundary(cell)
            cell_poly = Polygon([(lng, lat) for lat, lng in boundary])

            has_50_pct_coverage = False
            for ha in hazard_alerts:
                alert_poly = Polygon(ha.area.coordinates[0])
                if alert_poly.intersects(cell_poly):
                    inter_area = alert_poly.intersection(cell_poly).area
                    if (inter_area / cell_poly.area) >= 0.50:
                        has_50_pct_coverage = True
                        break

            if res.status == "official_hazard":
                assert has_50_pct_coverage, f"Cell {cell} marked official_hazard without independent 50% coverage at {t}"
            else:
                assert not has_50_pct_coverage or res.status == "official_hazard"


def test_status_never_contradicted_outside_groups(scenario: Scenario):
    """Cells outside all area groups have rain_available=False and never evaluate to contradicted."""
    outside_cell = "88618c4885fffff"  # Cell outside Chennai test bounding box
    now = scenario.t0 + timedelta(hours=5)
    inputs = scenario_inputs_at(scenario, now)
    feat = inputs.features_for_cell(outside_cell)
    assert feat.rain_available is False

    # Simulate positive hazard report in outside cell
    rep = [Report(id="out_r1", device_id="out_d1", cell=outside_cell, claim="flooded", created_at=now)]
    res = assess_cell(outside_cell, feat, rep, [], now)
    assert res.status == "unverified"
    assert res.status != "contradicted"


# --- 6. Extra Tuning and Structural Guarantees ---

def test_structural_guarantee_rumor_zone_prior_and_ceiling(scenario: Scenario):
    """Structural guarantee: for every simulated minute between 8h and 16h30 in rumor zone,
    prior p is in [0.06, 0.12] and sigmoid(prior_logit + 3.0) < 0.80.
    """
    rumor_cell = latlng_to_cell(13.055, 80.225, 8)

    for offset_s in range(28800, 59401, 60):
        t_eval = scenario.t0 + timedelta(seconds=offset_s)
        feat = features_for_cell(scenario, rumor_cell, t_eval)
        assert feat.flood_prone is False

        prior_logit = compute_prior_logit(feat)
        prior_p = sigmoid(prior_logit)
        post_clip = sigmoid(prior_logit + 3.0)

        assert 0.06 <= prior_p <= 0.12, f"Prior p out of bounds at offset {offset_s}: {prior_p:.4f}"
        assert post_clip < 0.80, f"Posterior with max clip exceeds 0.80 at offset {offset_s}: {post_clip:.4f}"


def test_alert_timing_isolation(scenario: Scenario):
    """Group 2 has no active hazard alert before 9h00; Rumor and Calm zones have no hazard alerts at any time."""
    adyar_cell = latlng_to_cell(13.015, 80.225, 8)
    rumor_cell = latlng_to_cell(13.055, 80.225, 8)
    calm_cell = latlng_to_cell(13.100, 80.160, 8)

    # 1. Before 9h00: Adyar has no active hazard alerts
    t_before_9h = scenario.t0 + timedelta(hours=8, minutes=59)
    inputs_before_9h = scenario_inputs_at(scenario, t_before_9h)
    feat_adyar = inputs_before_9h.features_for_cell(adyar_cell)
    res_adyar = assess_cell(adyar_cell, feat_adyar, inputs_before_9h.reports, inputs_before_9h.alerts, t_before_9h)
    assert res_adyar.status != "official_hazard"

    # 2. Rumor and calm zones never have hazard alerts
    for h in range(25):
        t_h = scenario.t0 + timedelta(hours=h)
        inputs_h = scenario_inputs_at(scenario, t_h)
        # Check alerts covering rumor cell
        f_rumor = inputs_h.features_for_cell(rumor_cell)
        res_rumor = assess_cell(rumor_cell, f_rumor, [], inputs_h.alerts, t_h)
        assert res_rumor.status != "official_hazard"

        # Check calm cell
        f_calm = inputs_h.features_for_cell(calm_cell)
        res_calm = assess_cell(calm_cell, f_calm, [], inputs_h.alerts, t_h)
        assert res_calm.status != "official_hazard"


def test_rumor_wave_clustering_counts(scenario: Scenario):
    """Verify wave clustering: scenario_inputs_at at 8h30 yields 1 cluster for rumor cell, at 10h45 yields 3."""
    rumor_cell = latlng_to_cell(13.055, 80.225, 8)

    # At 8h30
    t_8h30 = scenario.t0 + timedelta(hours=8, minutes=30)
    in_8h30 = scenario_inputs_at(scenario, t_8h30)
    clusters_8h30 = cluster_reports(in_8h30.reports, rumor_cell, t_8h30)
    active_clusters_8h30 = [c for c in clusters_8h30 if c.is_active]
    assert len(active_clusters_8h30) == 1

    # At 10h45
    t_10h45 = scenario.t0 + timedelta(hours=10, minutes=45)
    in_10h45 = scenario_inputs_at(scenario, t_10h45)
    clusters_10h45 = cluster_reports(in_10h45.reports, rumor_cell, t_10h45)
    active_clusters_10h45 = [c for c in clusters_10h45 if c.is_active]
    assert len(active_clusters_10h45) == 3


def test_scenario_bookmarks(scenario: Scenario):
    """Verify each bookmark in michaung_replay.json matches its narrative state."""
    adyar_cell = latlng_to_cell(13.015, 80.225, 8)
    rumor_cell = latlng_to_cell(13.055, 80.225, 8)
    calm_cell = latlng_to_cell(13.100, 80.160, 8)

    bm_map = {bm.name: bm for bm in scenario.bookmarks}

    # 1. early_warning (7h30)
    t_ew = scenario.t0 + timedelta(seconds=bm_map["early_warning"].t_offset_s)
    in_ew = scenario_inputs_at(scenario, t_ew)
    res_ew = assess_cell(adyar_cell, in_ew.features_for_cell(adyar_cell), in_ew.reports, in_ew.alerts, t_ew)
    assert res_ew.status == "likely_hazard"

    # 2. viral_rumor (8h30)
    t_vr = scenario.t0 + timedelta(seconds=bm_map["viral_rumor"].t_offset_s)
    in_vr = scenario_inputs_at(scenario, t_vr)
    res_vr = assess_cell(rumor_cell, in_vr.features_for_cell(rumor_cell), in_vr.reports, in_vr.alerts, t_vr)
    assert res_vr.status == "unverified"

    # 3. golden_moment (9h30: Adyar official_hazard, Rumor unverified, Calm clear)
    t_gm = scenario.t0 + timedelta(seconds=bm_map["golden_moment"].t_offset_s)
    in_gm = scenario_inputs_at(scenario, t_gm)
    res_gm_adyar = assess_cell(adyar_cell, in_gm.features_for_cell(adyar_cell), in_gm.reports, in_gm.alerts, t_gm)
    res_gm_rumor = assess_cell(rumor_cell, in_gm.features_for_cell(rumor_cell), in_gm.reports, in_gm.alerts, t_gm)
    res_gm_calm = assess_cell(calm_cell, in_gm.features_for_cell(calm_cell), in_gm.reports, in_gm.alerts, t_gm)
    assert res_gm_adyar.status == "official_hazard"
    assert res_gm_rumor.status == "unverified"
    assert res_gm_calm.status == "clear"

    # 4. all_clear_contradicted (11h30)
    t_acc = scenario.t0 + timedelta(seconds=bm_map["all_clear_contradicted"].t_offset_s)
    in_acc = scenario_inputs_at(scenario, t_acc)
    res_acc = assess_cell(rumor_cell, in_acc.features_for_cell(rumor_cell), in_acc.reports, in_acc.alerts, t_acc)
    assert res_acc.status == "contradicted"

    # 5. claims_aged_out (17h00)
    t_cao = scenario.t0 + timedelta(seconds=bm_map["claims_aged_out"].t_offset_s)
    in_cao = scenario_inputs_at(scenario, t_cao)
    res_cao = assess_cell(rumor_cell, in_cao.features_for_cell(rumor_cell), in_cao.reports, in_cao.alerts, t_cao)
    assert res_cao.status == "clear"


# --- 7. ReplayOverlay & Performance ---

def test_replay_overlay_dynamics(scenario: Scenario):
    """User report submitted during replay changes nothing at earlier seek times, appears at later times."""
    overlay = ReplayOverlay()
    t_submit = scenario.t0 + timedelta(hours=10)

    dynamic_rep = Report(
        id="dyn_rep_1",
        device_id="dyn_dev_1",
        cell="88618c4dadfffff",  # calm cell
        claim="flooded",
        created_at=t_submit,
    )
    overlay.add_report(dynamic_rep)

    # 1. At earlier seek time (9h): report is invisible
    t_early = scenario.t0 + timedelta(hours=9)
    in_early = scenario_inputs_at(scenario, t_early, overlay=overlay)
    assert not any(r.id == "dyn_rep_1" for r in in_early.reports)

    # 2. At later seek time (11h): report is visible
    t_late = scenario.t0 + timedelta(hours=11)
    in_late = scenario_inputs_at(scenario, t_late, overlay=overlay)
    assert any(r.id == "dyn_rep_1" for r in in_late.reports)


def test_performance_batch_assessment_bbox(scenario: Scenario):
    """Assess all res-8 cells covering the area groups bounding box in < 1.0 second."""
    t_eval = scenario.t0 + timedelta(hours=12)
    inputs = scenario_inputs_at(scenario, t_eval)

    # Bounding box covering all 5 groups
    cells = cells_in_bbox(12.95, 80.14, 13.12, 80.29, 8)
    assert len(cells) >= 50

    features_map = {c: inputs.features_for_cell(c) for c in cells}
    reports_by_cell: Dict[str, List[Report]] = {}
    for r in inputs.reports:
        reports_by_cell.setdefault(r.cell, []).append(r)

    t_start = time.perf_counter()
    assessments = assess_cells(cells, features_map, reports_by_cell, inputs.alerts, t_eval)
    elapsed = time.perf_counter() - t_start

    assert len(assessments) == len(cells)
    assert elapsed < 1.0, f"Batch assess_cells too slow: took {elapsed:.4f}s"
