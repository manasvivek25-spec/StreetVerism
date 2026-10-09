"""CAP (Common Alerting Protocol) XML ingestion and normalization for StreetVerism.

Supports CAP 1.2 namespace and namespace-less XML.
Uses defusedxml to guard against XXE and entity-expansion (billion laughs) vulnerabilities.
Converts CAP polygon 'lat,lng' text to GeoJSON [lng, lat] coordinate rings.
Emits one normalized Alert per <area> block using identifier indexing ({id}#1, {id}#2).
"""

import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import defusedxml.ElementTree as ET
from shapely.geometry import Point

from backend.app.db import to_utc_iso
from backend.app.ingest.manual import (
    SEVERITY_DEFAULT_DURATIONS,
    validate_and_repair_polygon,
)
from backend.app.models import Alert, GeoJSONPolygon

logger = logging.getLogger("streetverism.ingest.cap")

CAP_12_NAMESPACE = "urn:oasis:names:tc:emergency:cap:1.2"

# Enum Mapping Tables
SEVERITY_MAPPING = {
    "extreme": "extreme",
    "severe": "severe",
    "moderate": "moderate",
    "minor": "minor",
    "unknown": "minor",  # Default with warning
}

URGENCY_MAPPING = {
    "immediate": "immediate",
    "expected": "expected",
    "future": "future",
    "unknown": "expected",  # Default with warning
}

CERTAINTY_MAPPING = {
    "observed": "observed",
    "likely": "likely",
    "possible": "possible",
    "unlikely": "possible",  # Default with warning
    "unknown": "possible",   # Default with warning
}


def _strip_ns(tag: str) -> str:
    """Return local tag name stripped of XML namespace."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_elem(parent: Any, tag_name: str) -> Optional[Any]:
    """Find direct child element by local tag name."""
    for child in parent:
        if _strip_ns(child.tag) == tag_name:
            return child
    return None


def _find_all_elems(parent: Any, tag_name: str) -> List[Any]:
    """Find all direct child elements matching local tag name."""
    return [child for child in parent if _strip_ns(child.tag) == tag_name]


def _has_timezone_offset(ts_str: str) -> bool:
    """Check if ISO timestamp string contains an explicit timezone designator (+HH:MM, -HH:MM, or Z)."""
    ts = ts_str.strip()
    if ts.endswith("Z") or ts.endswith("z"):
        return True
    # Match +HH:MM or -HH:MM or +HHMM at the end
    return bool(re.search(r"[+-]\d{2}:?\d{2}$", ts))


def parse_cap_references(references_str: Optional[str]) -> List[str]:
    """Parse CAP references field formatted as whitespace-separated 'sender,identifier,sent' triplets.
    
    Returns list of referenced alert identifiers.
    """
    if not references_str or not references_str.strip():
        return []
    ids = []
    # Triplet format: sender,identifier,sent
    # References may be separated by space
    tokens = references_str.strip().split()
    for token in tokens:
        parts = token.split(",")
        if len(parts) >= 2:
            ids.append(parts[1].strip())
        elif len(parts) == 1 and parts[0]:
            ids.append(parts[0].strip())
    return ids


def map_cap_event_to_hazard(event: str, category: str, headline: str) -> str:
    """Map CAP event/category/headline text to our standard hazard vocabulary."""
    text = f"{event} {category} {headline}".lower()
    if "all clear" in text or "all-clear" in text or "cleared" in text or "safe" in text:
        return "all_clear"
    if "cyclone" in text or "hurricane" in text or "typhoon" in text or "storm" in text:
        return "cyclone"
    if "rain" in text or "downpour" in text or "precipitation" in text:
        return "heavy_rain"
    if "flood" in text or "inundation" in text or "waterlogging" in text or "met" in text:
        return "flood"
    logger.warning("Unrecognized CAP hazard event '%s'. Defaulting to 'flood'.", event)
    return "flood"


def cap_circle_to_polygon(circle_text: str) -> GeoJSONPolygon:
    """Convert CAP circle 'lat,lng radius_km' to GeoJSON polygon approximation."""
    parts = circle_text.strip().split()
    if len(parts) != 2:
        raise ValueError(f"Invalid CAP circle format: '{circle_text}'")
    coord_parts = parts[0].split(",")
    if len(coord_parts) != 2:
        raise ValueError(f"Invalid circle coordinates: '{parts[0]}'")
    lat = float(coord_parts[0].strip())
    lng = float(coord_parts[1].strip())
    radius_km = float(parts[1].strip())

    # Approximate 1 degree ~ 111 km
    deg_radius = radius_km / 111.0
    # Create buffered shapely circle point in (lng, lat)
    center = Point(lng, lat)
    poly = center.buffer(deg_radius, quad_segs=16)

    coords = [[round(pt[0], 6), round(pt[1], 6)] for pt in poly.exterior.coords]
    return GeoJSONPolygon(coordinates=[coords])


def parse_cap_polygon_string(poly_text: str) -> GeoJSONPolygon:
    """Parse CAP polygon string 'lat,lng lat,lng ...' and swap to GeoJSON [lng, lat] order with closed ring."""
    pairs = poly_text.strip().split()
    if len(pairs) < 3:
        raise ValueError("CAP polygon must have at least 3 coordinate pairs.")

    ring = []
    for pair in pairs:
        coords = pair.split(",")
        if len(coords) != 2:
            raise ValueError(f"Invalid lat,lng coordinate pair in CAP polygon: '{pair}'")
        lat = float(coords[0].strip())
        lng = float(coords[1].strip())
        # CRITICAL SWAP: CAP has (lat, lng); GeoJSON requires [lng, lat]
        ring.append([round(lng, 6), round(lat, 6)])

    # Ensure ring is closed
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])

    return validate_and_repair_polygon([ring])


def parse_cap_xml(xml_content: str, is_demo: bool = True) -> List[Alert]:
    """Parse CAP 1.2 or namespace-less XML into normalized Alert models.
    
    Returns a list of alerts (one per <area> polygon).
    Filters out non-Actual messages (Test/Exercise/Draft return empty list).
    Handles msgType='Cancel' and 'Update'.
    """
    root = ET.fromstring(xml_content)
    if _strip_ns(root.tag) != "alert":
        raise ValueError(f"Root XML element must be <alert>, found <{root.tag}>")

    identifier = (_find_elem(root, "identifier").text or "").strip() if _find_elem(root, "identifier") is not None else ""
    sender_raw = (_find_elem(root, "sender").text or "").strip() if _find_elem(root, "sender") is not None else "Unknown Authority"
    status = (_find_elem(root, "status").text or "").strip().lower() if _find_elem(root, "status") is not None else "actual"
    msg_type = (_find_elem(root, "msgType").text or "").strip().lower() if _find_elem(root, "msgType") is not None else "alert"
    sent_raw = (_find_elem(root, "sent").text or "").strip() if _find_elem(root, "sent") is not None else None
    references_raw = (_find_elem(root, "references").text or "").strip() if _find_elem(root, "references") is not None else None

    # Status check: only 'Actual' is ingested into live/evaluated state
    if status in ("test", "exercise", "draft"):
        logger.info("Skipping CAP alert %s with non-actual status: %s", identifier, status)
        return []

    if not sent_raw:
        raise ValueError(f"CAP alert {identifier} is missing required <sent> timestamp.")

    if not _has_timezone_offset(sent_raw):
        raise ValueError(f"CAP alert {identifier} <sent> timestamp '{sent_raw}' lacks required timezone offset.")

    sent_iso = to_utc_iso(sent_raw)
    superseded_ids = parse_cap_references(references_raw)

    # Sender naming rule: if demo, ensure (demo) suffix
    sender = sender_raw
    if is_demo and "(demo)" not in sender:
        sender = f"{sender} (demo)"

    # Select preferred <info> block (prefer language starts with 'en', else first)
    info_blocks = _find_all_elems(root, "info")
    if not info_blocks:
        if msg_type == "cancel" and superseded_ids:
            # CAP 1.2 permits omitting <info> for Cancel messages; emit minimal cancel alert to supersede reference
            dummy_poly = GeoJSONPolygon(coordinates=[[[0.0, 0.0], [0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]])
            return [
                Alert(
                    id=identifier or f"cancel_{superseded_ids[0]}",
                    source="official_cap",
                    sender=sender,
                    hazard="flood",
                    severity="minor",
                    urgency="immediate",
                    certainty="observed",
                    area=dummy_poly,
                    instruction_keys=["FOLLOW_OFFICIAL_ONLY"],
                    params={},
                    sent_at=sent_iso,
                    expires_at=sent_iso,
                    supersedes=superseded_ids[0],
                    published_by="cap_feed",
                    is_replay=False,
                )
            ]
        raise ValueError(f"CAP alert {identifier} contains no <info> elements.")

    selected_info = info_blocks[0]
    for info in info_blocks:
        lang_elem = _find_elem(info, "language")
        if lang_elem is not None and (lang_elem.text or "").strip().lower().startswith("en"):
            selected_info = info
            break
    logger.info("Selected CAP <info> block with language: %s", getattr(_find_elem(selected_info, "language"), "text", "default"))

    # Parse Severity
    sev_text = (_find_elem(selected_info, "severity").text or "").strip().lower() if _find_elem(selected_info, "severity") is not None else "minor"
    severity = SEVERITY_MAPPING.get(sev_text, "minor")
    if sev_text == "unknown" or sev_text not in SEVERITY_MAPPING:
        logger.warning("CAP severity '%s' mapped to fallback '%s'.", sev_text, severity)

    # Parse Urgency
    urg_text = (_find_elem(selected_info, "urgency").text or "").strip().lower() if _find_elem(selected_info, "urgency") is not None else "expected"
    if urg_text == "past":
        logger.info("CAP alert %s urgency is 'Past'. Skipping.", identifier)
        return []
    urgency = URGENCY_MAPPING.get(urg_text, "expected")
    if urg_text == "unknown" or urg_text not in URGENCY_MAPPING:
        logger.warning("CAP urgency '%s' mapped to fallback '%s'.", urg_text, urgency)

    # Parse Certainty
    cert_text = (_find_elem(selected_info, "certainty").text or "").strip().lower() if _find_elem(selected_info, "certainty") is not None else "possible"
    certainty = CERTAINTY_MAPPING.get(cert_text, "possible")
    if cert_text in ("unknown", "unlikely") or cert_text not in CERTAINTY_MAPPING:
        logger.warning("CAP certainty '%s' mapped to fallback '%s'.", cert_text, certainty)

    # Parse Expires
    if msg_type == "cancel":
        # Cancel expires referenced alerts immediately; expires_at = sent_iso
        exp_iso = sent_iso
    else:
        expires_elem = _find_elem(selected_info, "expires")
        if expires_elem is not None and expires_elem.text and expires_elem.text.strip():
            exp_raw = expires_elem.text.strip()
            if not _has_timezone_offset(exp_raw):
                raise ValueError(f"CAP alert {identifier} <expires> timestamp '{exp_raw}' lacks required timezone offset.")
            exp_iso = to_utc_iso(exp_raw)
        else:
            sent_dt = datetime.fromisoformat(sent_iso.replace("Z", "+00:00"))
            default_dur = SEVERITY_DEFAULT_DURATIONS.get(severity, timedelta(hours=12))
            exp_iso = to_utc_iso(sent_dt + default_dur)
            logger.warning("Missing <expires> tag in CAP alert %s. Defaulting to %s from severity '%s'.", identifier, exp_iso, severity)

    # Hazard classification
    event_str = (_find_elem(selected_info, "event").text or "") if _find_elem(selected_info, "event") is not None else ""
    cat_str = (_find_elem(selected_info, "category").text or "") if _find_elem(selected_info, "category") is not None else ""
    headline_str = (_find_elem(selected_info, "headline").text or "") if _find_elem(selected_info, "headline") is not None else ""
    hazard = map_cap_event_to_hazard(event_str, cat_str, headline_str)
    if msg_type == "cancel" and hazard == "all_clear":
        # Cancel must NOT establish all_clear status
        hazard = "flood"

    # Instructions parsing
    instruction_elem = _find_elem(selected_info, "instruction")
    instruction_text = (instruction_elem.text or "").strip() if instruction_elem is not None else ""
    instruction_keys = []
    if msg_type == "cancel":
        instruction_keys.append("FOLLOW_OFFICIAL_ONLY")
    elif hazard == "all_clear":
        instruction_keys.append("ALL_CLEAR")
    else:
        # Default safety actions
        instruction_keys.append("MOVE_TO_HIGHER_GROUND")
        if "flood" in instruction_text.lower() or "road" in instruction_text.lower():
            instruction_keys.append("AVOID_FLOODED_ROADS")

    # Areas parsing: emit ONE normalized Alert per polygon
    area_blocks = _find_all_elems(selected_info, "area")
    if not area_blocks:
        raise ValueError(f"CAP alert {identifier} contains no <area> blocks.")

    normalized_alerts: List[Alert] = []
    area_index = 1

    for area_elem in area_blocks:
        polygon_elem = _find_elem(area_elem, "polygon")
        circle_elem = _find_elem(area_elem, "circle")

        area_polygon: Optional[GeoJSONPolygon] = None
        if polygon_elem is not None and polygon_elem.text and polygon_elem.text.strip():
            area_polygon = parse_cap_polygon_string(polygon_elem.text.strip())
        elif circle_elem is not None and circle_elem.text and circle_elem.text.strip():
            area_polygon = cap_circle_to_polygon(circle_elem.text.strip())
        else:
            logger.warning("Area in CAP alert %s has neither valid polygon nor circle. Skipping area.", identifier)
            continue

        alert_id = f"{identifier}#{area_index}" if len(area_blocks) > 1 else identifier
        area_index += 1

        normalized_alerts.append(
            Alert(
                id=alert_id,
                source="official_cap",
                sender=sender,
                hazard=hazard,
                severity=severity,
                urgency=urgency,
                certainty=certainty,
                area=area_polygon,
                instruction_keys=instruction_keys,
                params={"instruction_text": instruction_text} if instruction_text else {},
                sent_at=sent_iso,
                expires_at=exp_iso,
                supersedes=superseded_ids[0] if superseded_ids else None,
                published_by="cap_feed",
                is_replay=False,
            )
        )

    return normalized_alerts
