"""Official disaster alert publishing, listing, and soft expiration service."""

from typing import List, Optional
from fastapi import HTTPException, status

from backend.app.ingest.lifecycle import get_active_alerts
from backend.app.ingest.manual import normalize_manual_alert
from backend.app.models import Alert, AlertCreate, AlertExpireResponse, AlertListResponse
from backend.app.repositories import AlertRepo
from backend.app.services.cells_service import clear_cells_cache
from backend.app.services.context import DataContext


def create_official_alert(
    payload: AlertCreate,
    ctx: DataContext,
    alert_repo: AlertRepo,
) -> Alert:
    """Validate and publish a new official emergency alert or all-clear notice.

    Replay mode guard: Returns 409 Conflict to protect synthetic replay state.
    """
    if ctx.mode == "replay":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="stop the replay with POST /scenario/reset to publish live alerts",
        )

    # Validate and normalize alert payload
    try:
        normalized = normalize_manual_alert(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[str(e)],
        )

    # Store normalized alert in database
    created = alert_repo.add(normalized)

    # Clear cells evaluation cache
    clear_cells_cache()

    return created


def list_official_alerts(
    active: bool,
    ctx: DataContext,
    alert_repo: AlertRepo,
) -> AlertListResponse:
    """List published official alerts.

    In replay mode, returns scenario alerts active at simulated clock time.
    In live mode, queries the database with dynamic lifecycle filtering.
    """
    if ctx.mode == "replay":
        alerts = list(ctx.alerts) if active else list(ctx.alerts)
        return AlertListResponse(alerts=alerts, total=len(alerts))

    all_alerts = alert_repo.list_all()
    if active:
        now_iso = ctx.now.isoformat()
        alerts = get_active_alerts(all_alerts, now_iso)
    else:
        alerts = all_alerts

    return AlertListResponse(alerts=alerts, total=len(alerts))


def expire_official_alert(
    alert_id: str,
    ctx: DataContext,
    alert_repo: AlertRepo,
) -> AlertExpireResponse:
    """Soft-expire an active alert by updating its expires_at timestamp to now."""
    now_iso = ctx.now.isoformat()
    success = alert_repo.expire(alert_id, now_iso)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")

    # Clear cells evaluation cache
    clear_cells_cache()

    return AlertExpireResponse(ok=True, id=alert_id, expired_at=now_iso)
