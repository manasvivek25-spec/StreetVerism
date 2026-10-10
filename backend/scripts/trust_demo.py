import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.geo import cell_to_polygon_lnglat
from backend.app.models.alert import Alert, GeoJSONPolygon
from backend.app.trust import (
    CellFeatures,
    Report,
    assess_cell,
)

ANCHOR_CELL = "88618c4f3dfffff"


def make_report(
    idx: int,
    claim: str = "flooded",
    text: str = None,
    created_at: datetime = None,
    tier: str = "default",
) -> Report:
    return Report(
        id=f"rep_{idx}",
        device_id=f"dev_{idx}",
        cell=ANCHOR_CELL,
        claim=claim,
        text=text,
        created_at=created_at or datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc),
        tier=tier,
    )


def make_all_clear_alert(cell: str, sent_at: datetime) -> Alert:
    poly = cell_to_polygon_lnglat(cell)[0]
    return Alert(
        id="alt_all_clear_demo",
        source="official_manual",
        sender="State Disaster Authority (demo)",
        hazard="all_clear",
        severity="minor",
        urgency="immediate",
        certainty="observed",
        area=GeoJSONPolygon(coordinates=[poly]),
        instruction_keys=["ALL_CLEAR"],
        params={},
        sent_at=sent_at.isoformat(),
        expires_at=(sent_at + timedelta(hours=12)).isoformat(),
        supersedes=None,
        published_by="operator",
        is_replay=False,
    )


def run_scenarios():
    now = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)

    scenarios = []

    # Scenario 1: Single fresh rumor on dry cell -> contradicted
    feat_dry = CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=False, rain_available=True)
    rep_1 = [make_report(1, "flooded", None, now)]
    res_1 = assess_cell(ANCHOR_CELL, feat_dry, rep_1, [], now)
    scenarios.append(("Single fresh rumor on dry cell", feat_dry, len(rep_1), res_1))

    # Scenario 2: Single rumor on flood-prone cell -> unverified
    feat_fp = CellFeatures(rain_mm_3h=0.0, rain_mm_24h=0.0, flood_prone=True, rain_available=True)
    rep_2 = [make_report(1, "flooded", None, now)]
    res_2 = assess_cell(ANCHOR_CELL, feat_fp, rep_2, [], now)
    scenarios.append(("Single rumor on flood-prone cell", feat_fp, len(rep_2), res_2))

    # Scenario 3: 3 distinct reports with 25 mm/3h flood-prone -> likely
    feat_rain = CellFeatures(rain_mm_3h=25.0, rain_mm_24h=30.0, flood_prone=True, rain_available=True)
    rep_3 = [make_report(i, "flooded", None, now) for i in range(3)]
    res_3 = assess_cell(ANCHOR_CELL, feat_rain, rep_3, [], now)
    scenarios.append(("3 distinct reports with 25 mm rain (flood-prone)", feat_rain, len(rep_3), res_3))

    # Scenario 4: 50 duplicate reports with identical text -> same p as 1
    rep_dup = [make_report(i, "flooded", "Severe flooding at subway station", now) for i in range(50)]
    res_dup = assess_cell(ANCHOR_CELL, feat_fp, rep_dup, [], now)
    scenarios.append(("50 duplicate reports (same text)", feat_fp, len(rep_dup), res_dup))

    # Scenario 5: 100 distinct devices -> bounded by clip (+3.0)
    rep_100 = [make_report(i, "flooded", None, now) for i in range(100)]
    res_100 = assess_cell(ANCHOR_CELL, feat_dry, rep_100, [], now)
    scenarios.append(("100 distinct devices (crowd clip bound)", feat_dry, len(rep_100), res_100))

    # Scenario 6: Decay at 0 h, 2 h, 4 h, 6 h
    for hours in [0, 2, 4, 6]:
        eval_time = now + timedelta(hours=hours)
        rep_decay = [make_report(1, "flooded", None, now)]
        res_decay = assess_cell(ANCHOR_CELL, feat_rain, rep_decay, [], eval_time)
        scenarios.append((f"Decay check at t = +{hours} h (half-life 2 h)", feat_rain, 1, res_decay))

    # Scenario 7: Official all_clear contradicting a rumor
    alert_clr = [make_all_clear_alert(ANCHOR_CELL, now - timedelta(minutes=15))]
    rep_clr = [make_report(1, "flooded", None, now)]
    res_clr = assess_cell(ANCHOR_CELL, feat_rain, rep_clr, alert_clr, now)
    scenarios.append(("Official all_clear contradicting rumor", feat_rain, len(rep_clr), res_clr))

    print("| Scenario | Rain 3h | Rain 24h | Terrain | Reports | Raw Crowd | Clipped | Prior p | Final p | Status | Headline Key |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for name, feat, num_rep, res in scenarios:
        fp_str = "Flood-prone" if feat.flood_prone else "Normal"
        r3_str = f"{feat.rain_mm_3h:.1f} mm" if feat.rain_mm_3h is not None else "0.0 mm"
        r24_str = f"{feat.rain_mm_24h:.1f} mm" if feat.rain_mm_24h is not None else "0.0 mm"
        prior_p = 1.0 / (1.0 + math.exp(-res.prior_logit))
        print(
            f"| {name} | {r3_str} | {r24_str} | {fp_str} | {num_rep} | {res.crowd_logit_raw:+.2f} | {res.crowd_logit_clipped:+.2f} | {prior_p:.3f} | {res.p_hazard:.3f} | `{res.status}` | `{res.headline_key}` |"
        )


if __name__ == "__main__":
    run_scenarios()
