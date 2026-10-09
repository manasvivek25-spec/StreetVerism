"""Alert lifecycle, temporal expiry, and supersede resolution engine.

Pure functions with injectable clock.
Guarantees:
- Temporal activity: sent_at <= now < expires_at.
- Supersede timing: a supersede takes effect ONLY when the superseding alert's sent_at <= now.
- Irreversibility: a superseded alert remains superseded forever; it never revives even if its replacement expires.
- Cycle guard: cycles (A supersedes B supersedes A) are detected, logged, and broken by preserving the alert with later sent_at.
- Audit trail: manual expiry sets expires_at = now, preserving historical record without hard deletion.
- all_clear distinction: all_clear alerts are maintained distinctly for trust engine Bayesian evidence overrides.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from backend.app.db import to_utc_iso
from backend.app.models import Alert

logger = logging.getLogger("streetverism.ingest.lifecycle")


def _to_utc_datetime(dt_or_iso: datetime | str) -> datetime:
    """Helper converting datetime or ISO string to UTC-aware datetime."""
    if isinstance(dt_or_iso, str):
        clean = dt_or_iso.strip()
        if clean.endswith("Z"):
            clean = clean[:-1] + "+00:00"
        dt = datetime.fromisoformat(clean)
    else:
        dt = dt_or_iso
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_temporally_active(alert: Alert, now: datetime | str) -> bool:
    """Check if alert is currently within its active temporal window: sent_at <= now < expires_at."""
    now_dt = _to_utc_datetime(now)
    sent_dt = _to_utc_datetime(alert.sent_at)
    exp_dt = _to_utc_datetime(alert.expires_at)
    return sent_dt <= now_dt < exp_dt


def resolve_superseded_ids(alerts: List[Alert], now: datetime | str) -> Set[str]:
    """Resolve the set of alert IDs that have been superseded as of `now`.
    
    Rules:
    1. A supersede takes effect ONLY when superseding alert's sent_at <= now.
    2. A superseded alert remains superseded even if its replacement later expires.
    3. Handles multi-hop chains (A superseded by B superseded by C).
    4. Cycle guard: cycles (A supersedes B supersedes A) are detected and broken by keeping the alert with later sent_at.
    5. Unknown references are safely logged and ignored.
    """
    now_dt = _to_utc_datetime(now)
    alert_map: Dict[str, Alert] = {a.id: a for a in alerts}

    # Step 1: Build effective supersede edges: source -> target (source supersedes target)
    edges: Dict[str, str] = {}
    for alert in alerts:
        if alert.supersedes:
            target_id = alert.supersedes
            sent_dt = _to_utc_datetime(alert.sent_at)

            # Supersede takes effect only when superseding alert has been published
            if sent_dt <= now_dt:
                if target_id not in alert_map:
                    logger.warning("Alert %s references unknown superseded alert ID '%s'. Ignoring reference.", alert.id, target_id)
                    continue
                edges[alert.id] = target_id

    # Step 2: Cycle detection & resolution
    # Detect 2-cycles (A -> B and B -> A) and general cycles
    # For any pair where edges[A] == B and edges[B] == A:
    # Compare sent_at: keep edge from the later alert; drop edge from the earlier alert.
    resolved_edges: Dict[str, str] = dict(edges)
    for src, tgt in list(edges.items()):
        if edges.get(tgt) == src:
            logger.warning("Supersede cycle detected between %s and %s. Breaking cycle.", src, tgt)
            src_sent = _to_utc_datetime(alert_map[src].sent_at)
            tgt_sent = _to_utc_datetime(alert_map[tgt].sent_at)
            if src_sent >= tgt_sent:
                # src is newer; drop tgt -> src edge
                if tgt in resolved_edges:
                    del resolved_edges[tgt]
            else:
                # tgt is newer; drop src -> tgt edge
                if src in resolved_edges:
                    del resolved_edges[src]

    # Step 3: Compute all superseded IDs by traversing chain
    superseded_ids: Set[str] = set()
    for src, tgt in resolved_edges.items():
        curr = tgt
        visited = set()
        while curr and curr not in visited:
            visited.add(curr)
            superseded_ids.add(curr)
            curr = resolved_edges.get(curr)

    return superseded_ids


def is_active(alert: Alert, now: datetime | str, superseded_ids: Set[str]) -> bool:
    """An alert is active if it is temporally active and not in superseded_ids."""
    return is_temporally_active(alert, now) and alert.id not in superseded_ids


def get_active_alerts(alerts: List[Alert], now: datetime | str) -> List[Alert]:
    """Return all currently active alerts, ordered by sent_at descending."""
    superseded = resolve_superseded_ids(alerts, now)
    active = [a for a in alerts if is_active(a, now, superseded)]
    return sorted(active, key=lambda a: _to_utc_datetime(a.sent_at), reverse=True)


def separate_all_clear_alerts(alerts: List[Alert]) -> Tuple[List[Alert], List[Alert]]:
    """Separate alerts into (hazard_alerts, all_clear_alerts).
    
    Active all_clear alerts are maintained distinctly so the trust engine (A2)
    can use their official geometry to override crowd hazard reports as contradicted.
    """
    hazard_alerts = [a for a in alerts if a.hazard != "all_clear"]
    all_clear_alerts = [a for a in alerts if a.hazard == "all_clear"]
    return hazard_alerts, all_clear_alerts


def expire_alert_now(alert: Alert, now: datetime | str) -> Alert:
    """Soft-expire an alert by setting expires_at = now, preserving audit trail."""
    now_iso = to_utc_iso(now)
    updated = alert.model_copy()
    updated.expires_at = now_iso
    return updated
