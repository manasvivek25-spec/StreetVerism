"""Tourist check-in submission, latest-per-device triage clustering, and 48h retention purging."""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException

from backend.app.geo import cell_to_parent, latlng_to_cell
from backend.app.models import (
    CheckinCluster,
    CheckinCreate,
    CheckinCreateResponse,
    CheckinItem,
    CheckinListResponse,
    CheckinUpdate,
)
from backend.app.repositories import CheckinRepo, ReportRepo
from backend.app.scenario import ReplayOverlay
from backend.app.services.context import DataContext
from backend.app.services.templates import SUPPORTED_LANGUAGES

RETENTION_WINDOW_HOURS: int = 48


def validate_checkin_payload(payload: CheckinCreate) -> None:
    """Validate check-in submission fields."""
    # 1. UUID device_id
    try:
        uuid.UUID(str(payload.device_id))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="Invalid device_id: must be a valid UUID string.")

    # 2. Coordinate ranges
    if not (-90.0 <= payload.lat <= 90.0):
        raise HTTPException(status_code=422, detail=f"Latitude {payload.lat} out of range [-90.0, 90.0].")
    if not (-180.0 <= payload.lng <= 180.0):
        raise HTTPException(status_code=422, detail=f"Longitude {payload.lng} out of range [-180.0, 180.0].")

    # 3. State enum
    if payload.state not in ("safe", "need_help"):
        raise HTTPException(status_code=422, detail="Invalid state: must be 'safe' or 'need_help'.")

    # 4. Language in six supported codes
    if payload.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid language '{payload.language}'. Must be one of: {', '.join(SUPPORTED_LANGUAGES)}.",
        )

    # 5. Group size 1-50
    if not (1 <= payload.group_size <= 50):
        raise HTTPException(status_code=422, detail="group_size must be an integer between 1 and 50.")

    # 6. Note <= 280 chars
    if payload.note and len(payload.note) > 280:
        raise HTTPException(status_code=422, detail="Check-in note exceeds maximum length of 280 characters.")


def submit_checkin(
    payload: CheckinCreate,
    ctx: DataContext,
    checkin_repo: CheckinRepo,
) -> CheckinCreateResponse:
    """Process, validate, and persist a tourist safety check-in."""
    validate_checkin_payload(payload)

    # Compute parent H3 resolution-7 cell for neighborhood triage
    cell8 = latlng_to_cell(payload.lat, payload.lng, 8)
    cell7 = cell_to_parent(cell8, 7)

    now_iso = ctx.now.isoformat()
    record = checkin_repo.add(
        checkin=payload,
        cell7=cell7,
        recorded_at=now_iso,
        is_replay=ctx.is_replay,
    )

    return CheckinCreateResponse(id=record.id, recorded_at=record.recorded_at or now_iso)


def list_checkins(checkin_repo: CheckinRepo) -> CheckinListResponse:
    """Retrieve check-ins deduplicated by device_id alongside aggregated triage clusters.

    Business Rules:
    - Latest check-in per device (newer check-in supersedes older ones).
    - If a device checks in again after being handled, the new one is unhandled.
    - device_id is stripped from public/authority view (privacy guarantee).
    - Clusters by cell7 calculate count, need_help, languages, and unhandled_need_help.
    - Sorting: Unhandled need_help items first, then newest.
    """
    all_checkins = checkin_repo.list_all()

    # Deduplicate keeping only latest check-in per device_id
    device_latest: Dict[str, CheckinItem] = {}
    for chk in all_checkins:
        dev_id = chk.device_id or chk.id
        ts = chk.created_at or chk.recorded_at or ""
        if dev_id not in device_latest:
            device_latest[dev_id] = chk
        else:
            prev_ts = device_latest[dev_id].created_at or device_latest[dev_id].recorded_at or ""
            if ts > prev_ts:
                device_latest[dev_id] = chk

    latest_items = list(device_latest.values())

    # Build sanitized output items (device_id stripped for location privacy)
    sanitized_items: List[CheckinItem] = []
    for item in latest_items:
        clean = item.model_copy()
        clean.device_id = None
        sanitized_items.append(clean)

    # Sort items: unhandled need_help first, then newest created_at descending
    def item_sort_key(i: CheckinItem):
        is_unhandled_need_help = 1 if (i.state == "need_help" and not i.handled) else 0
        ts = i.created_at or i.recorded_at or ""
        return (-is_unhandled_need_help, -datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())

    try:
        sanitized_items.sort(key=item_sort_key)
    except Exception:
        sanitized_items.sort(key=lambda i: (0 if (i.state == "need_help" and not i.handled) else 1))

    # Aggregate clusters by cell7
    cluster_groups: Dict[str, List[CheckinItem]] = defaultdict(list)
    for item in sanitized_items:
        cluster_groups[item.cell7].append(item)

    clusters: List[CheckinCluster] = []
    for cell7, group in cluster_groups.items():
        count = len(group)
        need_help_count = sum(1 for i in group if i.state == "need_help")
        unhandled_need_help_count = sum(1 for i in group if i.state == "need_help" and not i.handled)
        langs: Dict[str, int] = defaultdict(int)
        for i in group:
            langs[i.language] += 1

        clusters.append(
            CheckinCluster(
                cell7=cell7,
                count=count,
                need_help=need_help_count,
                languages=dict(langs),
                unhandled_need_help=unhandled_need_help_count,
            )
        )

    # Sort clusters by unhandled_need_help descending, then count descending
    clusters.sort(key=lambda c: (-c.unhandled_need_help, -c.need_help, -c.count))

    return CheckinListResponse(items=sanitized_items, clusters=clusters)


def handle_checkin(checkin_id: str, payload: CheckinUpdate, checkin_repo: CheckinRepo) -> CheckinItem:
    """Update handling status of a tourist check-in record."""
    updated = checkin_repo.set_handled(checkin_id, payload.handled)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Check-in {checkin_id} not found")
    clean = updated.model_copy()
    clean.device_id = None
    return clean


def purge_expired(
    now: datetime,
    checkin_repo: CheckinRepo,
    report_repo: ReportRepo,
    overlay: Optional[ReplayOverlay] = None,
) -> int:
    """Pure retention function purging records older than 48 hours.

    Covers live SQLite reports, live/replay check-ins in the DB, and in-memory replay overlay.
    """
    cutoff = now - timedelta(hours=RETENTION_WINDOW_HOURS)
    cutoff_iso = cutoff.isoformat()

    purged_checkins = checkin_repo.delete_older_than(cutoff_iso)
    purged_reports = report_repo.delete_older_than(cutoff_iso)

    purged_overlay = 0
    if overlay is not None:
        # Purge reports older than 48h relative to sim clock
        reports = overlay.get_reports()
        kept = []
        for r in reports:
            try:
                r_dt = datetime.fromisoformat(r.created_at.replace("Z", "+00:00"))
                if r_dt >= cutoff:
                    kept.append(r)
                else:
                    purged_overlay += 1
            except ValueError:
                kept.append(r)
        overlay.clear()
        for r in kept:
            overlay.add_report(r)

    total_purged = purged_checkins + purged_reports + purged_overlay
    return total_purged
