"""StreetVerism Replay Demo: prints simulated timeline across Chennai representative zones."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.geo import latlng_to_cell
from backend.app.scenario import (
    REPLAY_DISCLAIMER,
    REPLAY_LABEL,
    load_scenario,
    scenario_inputs_at,
)
from backend.app.trust import assess_cell


def format_status_p(status: str, p: float) -> str:
    """Format assessment result as `status (0.xxx)`."""
    return f"`{status}` ({p:.2f})"


def run_timeline_demo():
    root = Path(__file__).resolve().parent.parent.parent
    scenario_path = root / "data" / "scenarios" / "michaung_replay.json"
    shelters_path = root / "data" / "shelters.json"

    scenario = load_scenario(scenario_path, shelters_path)
    t0 = scenario.t0
    ist_tz = timezone(timedelta(hours=5, minutes=30))

    # Identify representative cells for each group
    rep_cells = {}
    for group in scenario.area_groups:
        pt = group.representative_point
        cell = latlng_to_cell(pt.lat, pt.lng, 8)
        rep_cells[group.id] = (group.name, cell)

    print(f"# {scenario.name}")
    print(f"> **{REPLAY_LABEL}**: {REPLAY_DISCLAIMER}\n")
    print("## 24-Hour Simulated Reconstruction Timeline\n")

    # Table 1: Hourly Timeline
    headers = [
        "Sim Hour",
        "UTC Time",
        "IST Time",
        "Velachery (G1)",
        "Adyar (G2)",
        "Rumor Zone (G3)",
        "Coastal (G4)",
        "Calm Zone (G5)",
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")

    for h in range(25):
        t_eval = t0 + timedelta(hours=h)
        utc_str = t_eval.strftime("%H:%M")
        ist_eval = t_eval.astimezone(ist_tz)
        ist_str = ist_eval.strftime("%H:%M")

        inputs = scenario_inputs_at(scenario, t_eval)

        row_cells = []
        for gid in [
            "group_1_velachery",
            "group_2_adyar",
            "group_3_rumor",
            "group_4_coastal",
            "group_5_calm",
        ]:
            _, cell = rep_cells[gid]
            feat = inputs.features_for_cell(cell)
            res = assess_cell(cell, feat, inputs.reports, inputs.alerts, t_eval)
            row_cells.append(format_status_p(res.status, res.p_hazard))

        print(f"| +{h:02d} h | {utc_str}Z | {ist_str} IST | " + " | ".join(row_cells) + " |")

    # Table 2: Scenario Bookmarks
    print("\n## Key Storyline Bookmarks\n")
    bm_headers = [
        "Bookmark",
        "Offset",
        "IST Time",
        "Adyar (G2)",
        "Rumor Zone (G3)",
        "Calm Zone (G5)",
        "Narrative Description",
    ]
    print("| " + " | ".join(bm_headers) + " |")
    print("|" + "|".join(["---"] * len(bm_headers)) + "|")

    adyar_cell = rep_cells["group_2_adyar"][1]
    rumor_cell = rep_cells["group_3_rumor"][1]
    calm_cell = rep_cells["group_5_calm"][1]

    for bm in scenario.bookmarks:
        t_bm = t0 + timedelta(seconds=bm.t_offset_s)
        ist_bm = t_bm.astimezone(ist_tz).strftime("%H:%M")
        inputs_bm = scenario_inputs_at(scenario, t_bm)

        res_adyar = assess_cell(adyar_cell, inputs_bm.features_for_cell(adyar_cell), inputs_bm.reports, inputs_bm.alerts, t_bm)
        res_rumor = assess_cell(rumor_cell, inputs_bm.features_for_cell(rumor_cell), inputs_bm.reports, inputs_bm.alerts, t_bm)
        res_calm = assess_cell(calm_cell, inputs_bm.features_for_cell(calm_cell), inputs_bm.reports, inputs_bm.alerts, t_bm)

        hrs = bm.t_offset_s // 3600
        mins = (bm.t_offset_s % 3600) // 60
        off_str = f"+{hrs:02d}h{mins:02d}m"

        print(
            f"| `{bm.name}` | {off_str} | {ist_bm} IST | "
            f"{format_status_p(res_adyar.status, res_adyar.p_hazard)} | "
            f"{format_status_p(res_rumor.status, res_rumor.p_hazard)} | "
            f"{format_status_p(res_calm.status, res_calm.p_hazard)} | "
            f"{bm.description} |"
        )


if __name__ == "__main__":
    run_timeline_demo()
