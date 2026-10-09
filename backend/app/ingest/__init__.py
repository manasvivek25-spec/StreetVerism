"""Alert ingestion and lifecycle management package."""

from .cap import parse_cap_xml
from .lifecycle import (
    expire_alert_now,
    get_active_alerts,
    is_active,
    is_temporally_active,
    resolve_superseded_ids,
    separate_all_clear_alerts,
)
from .manual import normalize_manual_alert, validate_and_repair_polygon

__all__ = [
    "normalize_manual_alert",
    "validate_and_repair_polygon",
    "parse_cap_xml",
    "is_temporally_active",
    "resolve_superseded_ids",
    "is_active",
    "get_active_alerts",
    "separate_all_clear_alerts",
    "expire_alert_now",
]
