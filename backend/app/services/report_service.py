"""Crowd report intake service with device-cell rate limiting, overlay isolation, and immediate re-assessment."""

import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4
from fastapi import HTTPException, Response

from backend.app.geo import latlng_to_cell
from backend.app.models import Report, ReportCreate, ReportResponse
from backend.app.repositories import ReportRepo
from backend.app.scenario import ReplayOverlay
from backend.app.services.cells_service import clear_cells_cache
from backend.app.services.context import DataContext
from backend.app.trust import assess_cell

RATE_LIMIT_WINDOW_SECONDS: int = 600  # 10 minutes per device per cell


def validate_report_payload(payload: ReportCreate) -> None:
    """Validate report fields: device_id format, coordinate ranges, claim enum, and max text length."""
    if not payload.device_id or len(payload.device_id.strip()) == 0:
        raise HTTPException(status_code=422, detail="Invalid device_id: must not be empty.")

    # Validate coordinate ranges
    if not (-90.0 <= payload.lat <= 90.0):
        raise HTTPException(status_code=422, detail=f"Latitude {payload.lat} out of range [-90.0, 90.0].")
    if not (-180.0 <= payload.lng <= 180.0):
        raise HTTPException(status_code=422, detail=f"Longitude {payload.lng} out of range [-180.0, 180.0].")

    # Validate claim enum
    if payload.claim not in ("flooded", "blocked", "safe", "impassable", "normal"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid claim '{payload.claim}'. Must be one of: flooded, blocked, safe.",
        )

    # Validate text length
    if payload.text and len(payload.text) > 280:
        raise HTTPException(status_code=422, detail="Report text exceeds maximum length of 280 characters.")


def check_rate_limit(
    device_id: str,
    cell: str,
    ctx: DataContext,
    report_repo: ReportRepo,
    overlay: Optional[ReplayOverlay],
) -> None:
    """Enforce per-device per-cell rate limit of 1 report every 600 seconds.

    Raises 429 with Retry-After header if violated.
    """
    now_dt = ctx.now

    if ctx.mode == "replay":
        # Check in replay overlay
        if overlay is not None:
            for rep in overlay.get_reports_at(now_dt):
                if rep.device_id == device_id and rep.cell == cell:
                    rep_dt = rep.created_at if isinstance(rep.created_at, datetime) else datetime.fromisoformat(str(rep.created_at).replace("Z", "+00:00"))
                    elapsed = (now_dt - rep_dt).total_seconds()
                    if 0 <= elapsed < RATE_LIMIT_WINDOW_SECONDS:
                        retry_after = int(RATE_LIMIT_WINDOW_SECONDS - elapsed)
                        raise HTTPException(
                            status_code=429,
                            detail=f"Rate limit exceeded: only one report per cell every {RATE_LIMIT_WINDOW_SECONDS} seconds.",
                            headers={"Retry-After": str(max(1, retry_after))},
                        )
        return

    # Live mode: Check database records for this cell
    db_reports = report_repo.list_by_cell(cell)
    for r in db_reports:
        if r.get("device_id") == device_id:
            try:
                rep_dt = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
                elapsed = (now_dt - rep_dt).total_seconds()
                if 0 <= elapsed < RATE_LIMIT_WINDOW_SECONDS:
                    retry_after = int(RATE_LIMIT_WINDOW_SECONDS - elapsed)
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded: only one report per cell every {RATE_LIMIT_WINDOW_SECONDS} seconds.",
                        headers={"Retry-After": str(max(1, retry_after))},
                    )
            except ValueError:
                continue


def submit_crowd_report(
    payload: ReportCreate,
    ctx: DataContext,
    report_repo: ReportRepo,
    overlay: Optional[ReplayOverlay],
) -> ReportResponse:
    """Validate, rate-limit, persist, and re-assess cell hazard state."""
    # 1. Validation
    validate_report_payload(payload)

    # 2. Assign cell
    cell = latlng_to_cell(payload.lat, payload.lng, 8)

    # 3. Rate limiting check (429 if violated)
    check_rate_limit(payload.device_id, cell, ctx, report_repo, overlay)

    created_iso = ctx.now.isoformat()
    new_report_obj = Report(
        id=f"rep_{uuid4().hex[:8]}",
        device_id=payload.device_id,
        lat=round(payload.lat, 4),
        lng=round(payload.lng, 4),
        cell=cell,
        claim=payload.claim,
        text=payload.text,
        created_at=created_iso,
    )

    # 4. Storage (Replay -> in-memory overlay only; Live -> SQLite DB only)
    if ctx.mode == "replay":
        if overlay is None:
            raise RuntimeError("Replay mode active but ReplayOverlay is uninitialized")
        overlay.add_report(new_report_obj)
    else:
        report_repo.add(payload, cell, created_at=created_iso)

    # 5. Invalidate cells cache on report write
    clear_cells_cache()

    # 6. Re-assess the cell to compute NEW assessed status
    existing_reports = list(ctx.reports_by_cell.get(cell, []))
    updated_reports = existing_reports + [new_report_obj]
    features = ctx.features_provider(cell)
    new_assessment = assess_cell(cell, features, updated_reports, ctx.alerts, ctx.now)

    return ReportResponse(
        accepted=True,
        cell=cell,
        status=new_assessment.status,
    )
