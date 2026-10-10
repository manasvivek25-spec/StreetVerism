"""Scenario loader and validation for StreetVerism Replay Engine."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import ValidationError

from backend.app.geo import latlng_to_cell
from backend.app.ingest.manual import _get_vetted_template_keys, validate_and_repair_polygon
from backend.app.models.alert import Alert, GeoJSONPolygon
from backend.app.scenario.types import (
    AreaGroup,
    Bookmark,
    RainKeyframe,
    RepresentativePoint,
    Scenario,
    ScenarioReport,
)
from backend.app.trust.types import Report

# Chennai coordinate sanity bounding box
MIN_LAT = 12.8
MAX_LAT = 13.3
MIN_LNG = 80.1
MAX_LNG = 80.4


def _check_coord_point(lat: float, lng: float, location_desc: str) -> None:
    """Validate coordinate point falls strictly inside Chennai bounding box."""
    if not (MIN_LAT <= lat <= MAX_LAT):
        raise ValueError(
            f"Coordinate sanity violation at {location_desc}: latitude {lat} outside allowable range [{MIN_LAT}, {MAX_LAT}]."
        )
    if not (MIN_LNG <= lng <= MAX_LNG):
        raise ValueError(
            f"Coordinate sanity violation at {location_desc}: longitude {lng} outside allowable range [{MIN_LNG}, {MAX_LNG}]."
        )


def _check_geojson_polygon_coords(poly_coords: List[List[List[float]]], location_desc: str) -> None:
    """Validate all coordinates in GeoJSON polygon [lng, lat] pairs."""
    for r_idx, ring in enumerate(poly_coords):
        for p_idx, pt in enumerate(ring):
            if len(pt) < 2:
                raise ValueError(f"Malformed coordinate at {location_desc} ring {r_idx} pt {p_idx}: {pt}")
            lng, lat = pt[0], pt[1]
            _check_coord_point(lat, lng, f"{location_desc} ring {r_idx} pt {p_idx} [lng={lng}, lat={lat}]")


def _load_known_shelter_ids(shelters_path: Optional[Union[Path, str]] = None) -> Set[str]:
    """Load valid shelter IDs from data/shelters.json."""
    if shelters_path:
        p = Path(shelters_path)
    else:
        root = Path(__file__).resolve().parent.parent.parent.parent
        p = root / "data" / "shelters.json"

    if not p.exists():
        return set()

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
        return {s["id"] for s in data if isinstance(s, dict) and "id" in s}


def load_scenario(
    path: Union[Path, str],
    shelters_path: Optional[Union[Path, str]] = None,
) -> Scenario:
    """Load, validate, and project scenario data from JSON file."""
    scenario_path = Path(path)
    if not scenario_path.exists():
        raise FileNotFoundError(f"Scenario file not found at: {scenario_path}")

    with open(scenario_path, "r", encoding="utf-8") as f:
        try:
            raw_data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in scenario file {scenario_path}: {exc}") from exc

    if not isinstance(raw_data, dict):
        raise ValueError(f"Scenario root must be a JSON object, got {type(raw_data).__name__}")

    # Top-level required fields sanity
    for req in ("name", "label", "disclaimer", "t0", "duration_s", "area_groups", "alerts", "reports"):
        if req not in raw_data:
            raise ValueError(f"Missing required field at scenario root: '{req}'")

    duration_s = int(raw_data["duration_s"])

    # 1. Validate Area Groups
    raw_groups = raw_data.get("area_groups", [])
    area_groups: List[AreaGroup] = []
    group_ids: Set[str] = set()

    for g_idx, g in enumerate(raw_groups):
        loc = f"area_groups[{g_idx}]"
        if not isinstance(g, dict):
            raise ValueError(f"Expected dict at {loc}")

        gid = g.get("id")
        if not gid or gid in group_ids:
            raise ValueError(f"Invalid or duplicate group id at {loc}: '{gid}'")
        group_ids.add(gid)

        # Coordinate checks on representative point
        rep_pt = g.get("representative_point")
        if not isinstance(rep_pt, dict):
            raise ValueError(f"Missing representative_point at {loc}")
        _check_coord_point(float(rep_pt.get("lat", 0)), float(rep_pt.get("lng", 0)), f"{loc}.representative_point")

        # Coordinate checks on polygon
        poly = g.get("polygon")
        if not isinstance(poly, dict) or "coordinates" not in poly:
            raise ValueError(f"Missing or invalid polygon at {loc}")
        _check_geojson_polygon_coords(poly["coordinates"], f"{loc}.polygon")

        # Validate polygon geometry
        valid_poly = validate_and_repair_polygon(poly["coordinates"])

        # Keyframes check: sorted and within duration
        raw_kfs = g.get("keyframes", [])
        if not raw_kfs:
            raise ValueError(f"Area group at {loc} has no rain keyframes.")

        parsed_kfs: List[RainKeyframe] = []
        last_t = -1
        for k_idx, kf in enumerate(raw_kfs):
            k_loc = f"{loc}.keyframes[{k_idx}]"
            parsed_kf = RainKeyframe(**kf)
            if parsed_kf.t_offset_s < 0 or parsed_kf.t_offset_s > duration_s:
                raise ValueError(
                    f"Keyframe offset {parsed_kf.t_offset_s} out of bounds [0, {duration_s}] at {k_loc}"
                )
            if parsed_kf.t_offset_s <= last_t:
                raise ValueError(
                    f"Keyframes must be strictly sorted by t_offset_s (got {parsed_kf.t_offset_s} after {last_t}) at {k_loc}"
                )
            last_t = parsed_kf.t_offset_s
            parsed_kfs.append(parsed_kf)

        area_groups.append(
            AreaGroup(
                id=gid,
                name=g.get("name", gid),
                representative_point=RepresentativePoint(**rep_pt),
                polygon=valid_poly,
                keyframes=parsed_kfs,
            )
        )

    # 2. Validate Bookmarks
    raw_bms = raw_data.get("bookmarks", [])
    bookmarks: List[Bookmark] = []
    for b_idx, bm in enumerate(raw_bms):
        b_loc = f"bookmarks[{b_idx}]"
        parsed_bm = Bookmark(**bm)
        if parsed_bm.t_offset_s < 0 or parsed_bm.t_offset_s > duration_s:
            raise ValueError(
                f"Bookmark offset {parsed_bm.t_offset_s} out of bounds [0, {duration_s}] at {b_loc}"
            )
        bookmarks.append(parsed_bm)

    # 3. Validate Alerts
    vetted_keys = set(_get_vetted_template_keys())
    known_shelters = _load_known_shelter_ids(shelters_path)

    raw_alerts = raw_data.get("alerts", [])
    alerts: List[Alert] = []
    for a_idx, alt in enumerate(raw_alerts):
        a_loc = f"alerts[{a_idx}]"
        if not isinstance(alt, dict):
            raise ValueError(f"Expected dict at {a_loc}")

        # Check coordinates in alert area
        area = alt.get("area")
        if not isinstance(area, dict) or "coordinates" not in area:
            raise ValueError(f"Missing or invalid area at {a_loc}")
        _check_geojson_polygon_coords(area["coordinates"], f"{a_loc}.area")
        valid_poly = validate_and_repair_polygon(area["coordinates"])

        # Check temporal order
        sent_at_s = alt.get("sent_at")
        expires_at_s = alt.get("expires_at")
        if not sent_at_s or not expires_at_s:
            raise ValueError(f"Alert at {a_loc} must specify both sent_at and expires_at")

        sent_dt = datetime.fromisoformat(sent_at_s.replace("Z", "+00:00"))
        exp_dt = datetime.fromisoformat(expires_at_s.replace("Z", "+00:00"))
        if sent_dt >= exp_dt:
            raise ValueError(
                f"Alert sent_at ({sent_at_s}) must be strictly earlier than expires_at ({expires_at_s}) at {a_loc}"
            )

        # Check instruction keys
        inst_keys = alt.get("instruction_keys", [])
        for k in inst_keys:
            if k not in vetted_keys:
                raise ValueError(f"Unknown instruction key '{k}' at {a_loc}. Must be in {vetted_keys}")

        hazard = alt.get("hazard")
        if hazard == "all_clear":
            if "ALL_CLEAR" not in inst_keys:
                raise ValueError(f"Alert with hazard='all_clear' at {a_loc} must contain 'ALL_CLEAR' instruction key.")
        else:
            if not inst_keys:
                raise ValueError(f"Hazard alert ('{hazard}') at {a_loc} must have at least one instruction key.")

        # Check shelter param existence in shelters.json
        params = alt.get("params", {})
        shelter_id = params.get("shelter")
        if shelter_id:
            if known_shelters and shelter_id not in known_shelters:
                raise ValueError(
                    f"Alert at {a_loc} specifies unknown shelter ID '{shelter_id}' not found in shelters.json."
                )

        alt_copy = dict(alt)
        alt_copy["area"] = valid_poly
        alerts.append(Alert(**alt_copy))

    # 4. Validate Reports & compute H3 cell
    raw_reports = raw_data.get("reports", [])
    reports: List[Report] = []
    for r_idx, rep in enumerate(raw_reports):
        r_loc = f"reports[{r_idx}]"
        if not isinstance(rep, dict):
            raise ValueError(f"Expected dict at {r_loc}")

        lat = float(rep.get("lat", 0.0))
        lng = float(rep.get("lng", 0.0))
        _check_coord_point(lat, lng, f"{r_loc} [lat={lat}, lng={lng}]")

        cell = latlng_to_cell(lat, lng, 8)
        created_at_val = rep.get("created_at")
        if isinstance(created_at_val, str):
            dt = datetime.fromisoformat(created_at_val.replace("Z", "+00:00"))
        else:
            dt = created_at_val

        reports.append(
            Report(
                id=rep.get("id"),
                device_id=rep.get("device_id"),
                cell=cell,
                claim=rep.get("claim", "flooded"),
                text=rep.get("text"),
                created_at=dt,
                tier=rep.get("tier", "default"),
            )
        )

    t0_val = raw_data["t0"]
    if isinstance(t0_val, str):
        t0_dt = datetime.fromisoformat(t0_val.replace("Z", "+00:00"))
    else:
        t0_dt = t0_val

    return Scenario(
        name=raw_data["name"],
        label=raw_data["label"],
        disclaimer=raw_data["disclaimer"],
        based_on=raw_data["based_on"],
        is_replay=bool(raw_data.get("is_replay", True)),
        values_are_approximate=bool(raw_data.get("values_are_approximate", True)),
        t0=t0_dt,
        duration_s=duration_s,
        bookmarks=bookmarks,
        area_groups=area_groups,
        alerts=alerts,
        reports=reports,
    )
