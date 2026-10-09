"""Probabilistic Bayesian Trust Engine for StreetVerism.

MATHEMATICAL DERIVATION:
========================
Under the assumption of conditional independence of evidence signals given acute hazard state H in {1, 0}:
    P(H | E_1, ..., E_n) / P(~H | E_1, ..., E_n) = [P(H) / P(~H)] * PROD_{i=1}^n [P(E_i | H) / P(E_i | ~H)]

Taking natural logarithms maps odds multiplication to addition:
    logit(P(H | E)) = logit(P(H)) + SUM_{i=1}^n LLR(E_i)
where:
    logit(p) = ln(p / (1 - p))
    LLR(E_i) = ln(P(E_i | H) / P(E_i | ~H))

Logs make independent evidence additive.

PRIOR MODEL (HAND-SET):
=======================
logit(p0) = -4.0 + 0.04 * rain_3h + 0.01 * rain_24h + 1.5 * flood_prone
Note: Coefficients and base odds are HAND-SET and tuned for the replay crisis scenario,
NOT statistically fitted from large historical datasets.

CROWD RELIABILITY & LOG-LIKELIHOOD RATIOS:
==========================================
For an observer with sensitivity s = P(Pos | H) and specificity q = P(Neg | ~H):
    Positive claim (flooded / blocked): LLR_+ = ln(s / (1 - q))
    Safe claim (safe):                 LLR_- = ln((1 - s) / q)  (negative)

Tiers:
- default:        s = 0.70, q = 0.85
  LLR_+ = ln(0.70 / 0.15) = +1.540445...
  LLR_- = ln(0.30 / 0.85) = -1.041454...
- verified_local: s = 0.90, q = 0.95
  LLR_+ = ln(0.90 / 0.05) = +2.890372...
  LLR_- = ln(0.10 / 0.95) = -2.251292...

DEDUPLICATION & UNION-FIND CLUSTERING:
======================================
1. Filter: Drop reports with created_at > now (future) or older than 24 h. Ignore reports whose cell != target.
2. Rate-limit: Per (device_id, cell), anchor on the LAST KEPT report: keep a report only if >= 600 s
   after the last kept report.
3. Pathological Volume: Process at most MAX_REPORTS_PER_CELL (200) most recent reports.
4. Union-Find Clustering:
   - Same polarity only (positive vs safe never merge).
   - Time sweep window: pairwise Jaccard comparison only inside a 15-min (|dt| <= 900 s) window.
   - Linked if same device_id OR character-3-gram Jaccard similarity >= 0.60 on normalized lowercase text.
   - Empty/missing text never links by text (similarity 0.0).
   - Chaining behavior: Union-Find creates equivalence classes via transitive chaining (A ~ B and B ~ C => A ~ C).
5. Cluster Contribution:
   - Each cluster contributes ONE LLR = member with largest |LLR| (verified beats default).
   - Timestamp = cluster's EARLIEST report (conservative; re-posted rumors do not reset freshness).

EXPONENTIAL DECAY & BOUNDING:
=============================
Decay factor: exp(-lambda * dt), half-life = 2 h (7200 s), lambda = ln(2) / 7200.
Crowd logit clamped to [-3.0, +3.0].
Rain enters ONLY via the prior; the rain evidence line is display-only with weight = prior contribution.

OFFICIAL OVERRIDE & CLASS UNIONS:
=================================
- Active alerts are separated into hazard class (hazard != all_clear) and all_clear class.
- The spatial union of polygons is computed for each class.
- A class qualifies if cell_polygon INTERSECT class_union area / cell_polygon area >= 0.50.
  (Degree-space area ratio is acceptable at this local scale of ~450 m res-8 cells).
- If both qualify: the class with the newer latest contributing sent_at decides (ties: hazard wins).
- Hazard override: official_hazard, p = 0.99.
- All-clear override: status clear (p = 0.01); BUT if active positive claims exist, contradicted (p = 0.01).

CLASSIFICATION RULES:
=====================
- likely_hazard: p >= 0.80 AND corroborated positive clusters >= 2.
- contradicted: active positive claims exist AND (a) official all_clear covers cell, OR
  (b) rain_available == True AND prior p < 0.05 AND corroborated positive clusters < 2.
  Rule (b) requires fresh rain data; if rain_available is False, lack of radar echo cannot prove safety,
  so the cell is classified as unverified, never contradicted.
- unverified: active positive claims exist (neither likely nor contradicted); OR no claims but p >= 0.50.
- clear: p < 0.50 and no active positive claims.
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from shapely.geometry import Polygon
from shapely.ops import unary_union

from backend.app.geo import cell_to_polygon_lnglat
from backend.app.models.alert import Alert
from backend.app.models.state import EvidenceItem
from backend.app.trust.types import CellAssessment, CellFeatures, Report

# --- Named Constants ---

# Prior formulation constants
PRIOR_INTERCEPT: float = -4.0
PRIOR_COEFF_RAIN_3H: float = 0.04
PRIOR_COEFF_RAIN_24H: float = 0.01
PRIOR_COEFF_FLOOD_PRONE: float = 1.50
MAX_RAIN_3H_MM: float = 150.0
MAX_RAIN_24H_MM: float = 400.0

# Exact theoretical LLRs
LLR_DEFAULT_POSITIVE: float = math.log(0.70 / (1.0 - 0.85))      # ~ +1.540445
LLR_DEFAULT_SAFE: float = math.log((1.0 - 0.70) / 0.85)          # ~ -1.041454
LLR_VERIFIED_POSITIVE: float = math.log(0.90 / (1.0 - 0.95))     # ~ +2.890372
LLR_VERIFIED_SAFE: float = math.log((1.0 - 0.90) / 0.95)         # ~ -2.251292

# Temporal decay and bounds
DECAY_HALF_LIFE_S: float = 7200.0                                # 2 hours
DECAY_LAMBDA: float = math.log(2.0) / DECAY_HALF_LIFE_S          # ln2 / 7200
CROWD_LOGIT_MIN: float = -3.0
CROWD_LOGIT_MAX: float = 3.0

# Cluster activity & corroboration thresholds (age in seconds)
ACTIVE_MAX_AGE_S: float = 21600.0                                # 6 hours
CORROBORATED_MAX_AGE_S: float = 14400.0                          # 4 hours
ACTIVE_DECAY_THRESHOLD: float = 0.125                            # derived: exp(-ln2/7200 * 21600) = 0.125
CORROBORATED_DECAY_THRESHOLD: float = 0.25                       # derived: exp(-ln2/7200 * 14400) = 0.25

# Classification thresholds
LIKELY_P_THRESHOLD: float = 0.80
LIKELY_MIN_CORROBORATED_CLUSTERS: int = 2
CONTRADICTED_PRIOR_P_THRESHOLD: float = 0.05
WEATHER_ELEVATED_P_THRESHOLD: float = 0.50
CLEAR_P_THRESHOLD: float = 0.50

# Spatial & Official override thresholds
OFFICIAL_OVERLAP_THRESHOLD: float = 0.50
OFFICIAL_EVIDENCE_WEIGHT: float = 3.5

# Volume & Rate-limiting constraints
DEVICE_RATE_LIMIT_WINDOW_S: float = 600.0                        # 10 minutes
CLUSTER_TIME_WINDOW_S: float = 900.0                             # 15 minutes
CLUSTER_TEXT_JACCARD_THRESHOLD: float = 0.60
MAX_REPORTS_PER_CELL: int = 200
MAX_REPORT_AGE_S: float = 86400.0                                # 24 hours

# Canonical Template Headline Keys
HEADLINE_MOVE_TO_HIGHER_GROUND = "MOVE_TO_HIGHER_GROUND"
HEADLINE_AVOID_FLOODED_ROADS = "AVOID_FLOODED_ROADS"
HEADLINE_UNVERIFIED_WARNING = "UNVERIFIED_WARNING"
HEADLINE_FOLLOW_OFFICIAL_ONLY = "FOLLOW_OFFICIAL_ONLY"
HEADLINE_ALL_CLEAR = "ALL_CLEAR"

# Evidence ranking for deterministic sorting
EVIDENCE_RANK = {"official": 0, "rain": 1, "crowd": 2}


# --- Pure Mathematical & Helper Functions ---

def sigmoid(x: float) -> float:
    """Numerically safe logistic sigmoid function avoiding float overflow."""
    if x >= 0.0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)


def clamp(val: float, low: float, high: float) -> float:
    """Clamp float value to [low, high] interval."""
    return max(low, min(val, high))


def _validate_now(now: datetime) -> datetime:
    """Enforce timezone-aware datetime and normalize to UTC."""
    if not isinstance(now, datetime):
        raise ValueError("now parameter must be a datetime instance.")
    if now.tzinfo is None or now.tzinfo.utcoffset(now) is None:
        raise ValueError("now parameter must be a timezone-aware datetime (UTC-aware).")
    return now.astimezone(timezone.utc)


def compute_prior_logit(features: CellFeatures) -> float:
    """Calculate prior logit odds from rainfall accumulation and terrain susceptibility."""
    r3 = features.rain_mm_3h if features.rain_mm_3h is not None and not math.isnan(features.rain_mm_3h) else 0.0
    r3 = max(0.0, min(float(r3), MAX_RAIN_3H_MM))

    r24 = features.rain_mm_24h if features.rain_mm_24h is not None and not math.isnan(features.rain_mm_24h) else 0.0
    r24 = max(0.0, min(float(r24), MAX_RAIN_24H_MM))

    fp = 1.0 if features.flood_prone else 0.0
    return PRIOR_INTERCEPT + (PRIOR_COEFF_RAIN_3H * r3) + (PRIOR_COEFF_RAIN_24H * r24) + (PRIOR_COEFF_FLOOD_PRONE * fp)


def char_3gram_jaccard(text1: Optional[str], text2: Optional[str]) -> float:
    """Compute character 3-gram Jaccard similarity between two text strings."""
    if not text1 or not text2:
        return 0.0
    norm1 = " ".join(text1.lower().split())
    norm2 = " ".join(text2.lower().split())
    if len(norm1) < 3 or len(norm2) < 3:
        return 0.0
    g1 = {norm1[i:i+3] for i in range(len(norm1) - 2)}
    g2 = {norm2[i:i+3] for i in range(len(norm2) - 2)}
    if not g1 or not g2:
        return 0.0
    intersection = len(g1 & g2)
    union = len(g1 | g2)
    return intersection / union if union > 0 else 0.0


def _get_report_llr(report: Report) -> float:
    """Return theoretical LLR for an individual report based on claim and tier."""
    if report.claim in ("flooded", "blocked"):
        return LLR_VERIFIED_POSITIVE if report.tier == "verified_local" else LLR_DEFAULT_POSITIVE
    elif report.claim == "safe":
        return LLR_VERIFIED_SAFE if report.tier == "verified_local" else LLR_DEFAULT_SAFE
    return 0.0


# --- Union-Find Data Structure ---

class UnionFind:
    """Disjoint-set union-find with path compression and union by rank."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, i: int) -> int:
        if self.parent[i] != i:
            self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: int, j: int):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            if self.rank[root_i] < self.rank[root_j]:
                self.parent[root_i] = root_j
            elif self.rank[root_i] > self.rank[root_j]:
                self.parent[root_j] = root_i
            else:
                self.parent[root_j] = root_i
                self.rank[root_i] += 1


class ClusterInfo:
    """Represents a deduplicated and clustered crowd evidence component."""

    def __init__(self, reports: List[Report], now: datetime):
        self.reports = sorted(reports, key=lambda r: (r.created_at, r.id))
        self.earliest_report = self.reports[0]
        self.claim = self.earliest_report.claim
        self.is_positive = self.claim in ("flooded", "blocked")

        # Pick report with largest |LLR|
        self.best_report = max(self.reports, key=lambda r: abs(_get_report_llr(r)))
        self.llr = _get_report_llr(self.best_report)

        # Decay based on earliest report timestamp
        self.dt_seconds = max(0.0, (now - self.earliest_report.created_at).total_seconds())
        self.decay_factor = math.exp(-DECAY_LAMBDA * self.dt_seconds)
        self.decayed_llr = self.llr * self.decay_factor

        # Age-based thresholds (exact seconds: age <= 6h active, age <= 4h corroborated)
        self.is_active = self.is_positive and (self.dt_seconds <= ACTIVE_MAX_AGE_S)
        self.is_corroborated = self.is_positive and (self.dt_seconds <= CORROBORATED_MAX_AGE_S)


# --- Core Clustering Logic ---

def cluster_reports(reports: List[Report], target_cell: str, now: datetime) -> List[ClusterInfo]:
    """Filter, rate-limit, and cluster reports for an H3 cell deterministically."""
    # 1. Filter: cell match, future dates, >24h old
    valid: List[Report] = []
    for r in reports:
        if r.cell != target_cell:
            continue
        dt = (now - r.created_at).total_seconds()
        if dt < 0.0 or dt > MAX_REPORT_AGE_S:
            continue
        valid.append(r)

    if not valid:
        return []

    # 2. Deterministic sort chronologically by (created_at, id)
    valid.sort(key=lambda r: (r.created_at, r.id))

    # 3. Device rate-limiting: anchor on LAST KEPT report per (device, cell)
    last_kept_by_device: Dict[str, datetime] = {}
    rate_limited: List[Report] = []
    for r in valid:
        last_time = last_kept_by_device.get(r.device_id)
        if last_time is None or (r.created_at - last_time).total_seconds() >= DEVICE_RATE_LIMIT_WINDOW_S:
            rate_limited.append(r)
            last_kept_by_device[r.device_id] = r.created_at

    # 4. Pathological volume cap: process at most 200 most recent
    if len(rate_limited) > MAX_REPORTS_PER_CELL:
        rate_limited = rate_limited[-MAX_REPORTS_PER_CELL:]

    n = len(rate_limited)
    if n == 0:
        return []

    # 5. Union-Find Clustering with 15-minute sweep window
    uf = UnionFind(n)
    for i in range(n):
        ri = rate_limited[i]
        pol_i = ri.claim in ("flooded", "blocked")
        for j in range(i - 1, -1, -1):
            rj = rate_limited[j]
            dt_s = (ri.created_at - rj.created_at).total_seconds()
            if dt_s > CLUSTER_TIME_WINDOW_S:
                # Outside 15-min window; since reports are sorted by time, break early
                break
            pol_j = rj.claim in ("flooded", "blocked")
            if pol_i != pol_j:
                # Opposite polarity never merges
                continue

            # Link condition: same device OR character 3-gram Jaccard >= 0.60
            if ri.device_id == rj.device_id or char_3gram_jaccard(ri.text, rj.text) >= CLUSTER_TEXT_JACCARD_THRESHOLD:
                uf.union(i, j)

    # Group into clusters
    groups: Dict[int, List[Report]] = {}
    for i in range(n):
        root = uf.find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(rate_limited[i])

    clusters = [ClusterInfo(members, now) for members in groups.values()]
    # Sort clusters deterministically by earliest report timestamp
    clusters.sort(key=lambda c: (c.earliest_report.created_at, c.earliest_report.id))
    return clusters


# --- Official Alert Geometries & Spatial Decision ---

class AlertGeoPrep:
    """Pre-processed official alert geometry and metadata."""

    def __init__(self, alert: Alert):
        self.alert = alert
        self.is_hazard = alert.hazard != "all_clear"
        self.sent_at_dt = datetime.fromisoformat(alert.sent_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        self.polygon = Polygon(alert.area.coordinates[0])


def _evaluate_official_override(
    cell_poly: Polygon,
    hazard_alerts: List[AlertGeoPrep],
    all_clear_alerts: List[AlertGeoPrep],
    hazard_union: Optional[Any],
    all_clear_union: Optional[Any],
    has_active_positive_claims: bool,
) -> Tuple[Optional[str], Optional[float], Optional[str], List[AlertGeoPrep], Optional[str]]:
    """Determine official alert override via class union coverage (>= 0.50).
    
    Returns:
        (status, p_hazard, headline_key, deciding_alerts, deciding_sender) or (None, None, None, [], None)
    """
    cell_area = cell_poly.area
    if cell_area <= 0.0:
        return None, None, None, [], None

    # Calculate class union coverage
    hazard_cov = (cell_poly.intersection(hazard_union).area / cell_area) if hazard_union and not hazard_union.is_empty else 0.0
    all_clear_cov = (cell_poly.intersection(all_clear_union).area / cell_area) if all_clear_union and not all_clear_union.is_empty else 0.0

    hazard_qualifies = hazard_cov >= OFFICIAL_OVERLAP_THRESHOLD
    all_clear_qualifies = all_clear_cov >= OFFICIAL_OVERLAP_THRESHOLD

    if not hazard_qualifies and not all_clear_qualifies:
        return None, None, None, [], None

    # Identify contributing alerts that have positive overlap with cell
    contributing_hazards = [a for a in hazard_alerts if cell_poly.intersects(a.polygon) and cell_poly.intersection(a.polygon).area > 0.0]
    contributing_clears = [a for a in all_clear_alerts if cell_poly.intersects(a.polygon) and cell_poly.intersection(a.polygon).area > 0.0]

    latest_hazard_dt = max((a.sent_at_dt for a in contributing_hazards), default=datetime.min.replace(tzinfo=timezone.utc))
    latest_clear_dt = max((a.sent_at_dt for a in contributing_clears), default=datetime.min.replace(tzinfo=timezone.utc))

    # Decision rule: if both qualify, latest sent_at decides; ties: hazard wins (fail-safe)
    if hazard_qualifies and all_clear_qualifies:
        if latest_hazard_dt >= latest_clear_dt:
            deciding_class = "hazard"
        else:
            deciding_class = "all_clear"
    elif hazard_qualifies:
        deciding_class = "hazard"
    else:
        deciding_class = "all_clear"

    if deciding_class == "hazard":
        # Official hazard override
        deciding_alert = max(contributing_hazards, key=lambda a: a.sent_at_dt)
        headline = deciding_alert.alert.instruction_keys[0] if deciding_alert.alert.instruction_keys else HEADLINE_MOVE_TO_HIGHER_GROUND
        return "official_hazard", 0.99, headline, contributing_hazards, deciding_alert.alert.sender
    else:
        # Official all-clear override
        deciding_alert = max(contributing_clears, key=lambda a: a.sent_at_dt)
        if has_active_positive_claims:
            # Contradicted takes precedence over clear when positive claims were active
            return "contradicted", 0.01, HEADLINE_FOLLOW_OFFICIAL_ONLY, contributing_clears, deciding_alert.alert.sender
        else:
            return "clear", 0.01, HEADLINE_ALL_CLEAR, contributing_clears, deciding_alert.alert.sender


# --- Public Module API ---

def assess_cell(
    cell: str,
    features: CellFeatures,
    reports: List[Report],
    alerts: List[Alert],
    now: datetime,
) -> CellAssessment:
    """Assess crisis hazard state for a single H3 cell with injected UTC clock.
    
    Pure, deterministic function with zero I/O and zero global state.
    """
    now_utc = _validate_now(now)

    # 1. Deduplicate & cluster crowd reports
    clusters = cluster_reports(reports, cell, now_utc)
    active_positive_clusters = [c for c in clusters if c.is_active]
    corroborated_positive_clusters = [c for c in clusters if c.is_corroborated]
    has_active_positive = len(active_positive_clusters) > 0

    # 2. Prior & Crowd Logits
    prior_logit = compute_prior_logit(features)
    prior_p = sigmoid(prior_logit)

    raw_crowd_logit = sum(c.decayed_llr for c in clusters)
    clipped_crowd_logit = clamp(raw_crowd_logit, CROWD_LOGIT_MIN, CROWD_LOGIT_MAX)

    posterior_logit = prior_logit + clipped_crowd_logit
    posterior_p = sigmoid(posterior_logit)

    # 3. Official Alert Spatial Preparation
    prepared_alerts = [AlertGeoPrep(a) for a in alerts]
    hazard_preps = [a for a in prepared_alerts if a.is_hazard]
    clear_preps = [a for a in prepared_alerts if not a.is_hazard]

    hazard_union = unary_union([a.polygon for a in hazard_preps]) if hazard_preps else None
    clear_union = unary_union([a.polygon for a in clear_preps]) if clear_preps else None

    cell_poly = Polygon(cell_to_polygon_lnglat(cell)[0])

    override_status, override_p, override_headline, deciding_official, deciding_sender = _evaluate_official_override(
        cell_poly,
        hazard_preps,
        clear_preps,
        hazard_union,
        clear_union,
        has_active_positive,
    )

    # 4. Status Classification State Machine
    official_alert_ids: List[str] = []
    if override_status is not None:
        status = override_status
        final_p = override_p
        headline_key = override_headline
        official_alert_ids = [a.alert.id for a in deciding_official]
    else:
        final_p = posterior_p
        if final_p >= LIKELY_P_THRESHOLD and len(corroborated_positive_clusters) >= LIKELY_MIN_CORROBORATED_CLUSTERS:
            status = "likely_hazard"
            headline_key = HEADLINE_AVOID_FLOODED_ROADS
        elif (
            has_active_positive
            and features.rain_available
            and prior_p < CONTRADICTED_PRIOR_P_THRESHOLD
            and len(corroborated_positive_clusters) < LIKELY_MIN_CORROBORATED_CLUSTERS
        ):
            # Contradicted via plausible low prior (requires fresh rain data)
            status = "contradicted"
            headline_key = HEADLINE_FOLLOW_OFFICIAL_ONLY
        elif has_active_positive or (not has_active_positive and final_p >= WEATHER_ELEVATED_P_THRESHOLD):
            # Unverified: active claims uncorroborated OR weather-only elevated risk
            status = "unverified"
            headline_key = HEADLINE_UNVERIFIED_WARNING
        else:
            status = "clear"
            headline_key = HEADLINE_FOLLOW_OFFICIAL_ONLY

    # 5. Build Deterministic Evidence Breakdown
    evidence_items: List[EvidenceItem] = []

    # (a) Official alert lines
    for a in deciding_official:
        evidence_items.append(
            EvidenceItem(
                type="official",
                summary=f"Official {a.alert.hazard.replace('_', ' ').title()} Alert from {a.alert.sender}",
                age_s=max(0, int((now_utc - a.sent_at_dt).total_seconds())),
                weight=OFFICIAL_EVIDENCE_WEIGHT,
            )
        )

    # (b) Rain evidence line (display only; weight = prior contribution)
    if features.rain_available:
        r3 = max(0.0, min(features.rain_mm_3h or 0.0, MAX_RAIN_3H_MM))
        r24 = max(0.0, min(features.rain_mm_24h or 0.0, MAX_RAIN_24H_MM))
        fp_note = "; flood-prone area" if features.flood_prone else ""
        rain_weight = (PRIOR_COEFF_RAIN_3H * r3) + (PRIOR_COEFF_RAIN_24H * r24) + (PRIOR_COEFF_FLOOD_PRONE * (1.0 if features.flood_prone else 0.0))
        evidence_items.append(
            EvidenceItem(
                type="rain",
                summary=f"Rain {r3:.1f} mm in 3 h, {r24:.1f} mm in 24 h{fp_note}",
                age_s=0,
                weight=round(rain_weight, 2),
            )
        )

    # (c) Crowd evidence lines
    for c in clusters:
        if status == "contradicted":
            if override_status == "contradicted" and deciding_sender:
                summary = f"Claim contradicted by official all-clear from {deciding_sender} ({c.claim}) (unverified)"
            else:
                summary = "No heavy rain recorded here, so this report is unconfirmed. Follow official guidance."
        else:
            count = len(c.reports)
            if count == 1:
                summary = f"1 report ({c.claim}) (unverified)"
            else:
                summary = f"{count} similar reports counted as 1 ({c.claim}) (unverified)"

        evidence_items.append(
            EvidenceItem(
                type="crowd",
                summary=summary,
                age_s=int(c.dt_seconds),
                weight=round(c.decayed_llr, 2),
            )
        )

    # Deterministic sort: official (rank 0), rain (rank 1), crowd (rank 2 by age_s, summary)
    evidence_items.sort(key=lambda e: (EVIDENCE_RANK[e.type], e.age_s, e.summary))

    return CellAssessment(
        cell=cell,
        status=status,
        p_hazard=round(final_p, 4),
        headline_key=headline_key,
        prior_logit=round(prior_logit, 4),
        crowd_logit_raw=round(raw_crowd_logit, 4),
        crowd_logit_clipped=round(clipped_crowd_logit, 4),
        posterior_logit=round(posterior_logit, 4),
        evidence=evidence_items,
        cluster_count_positive=len(active_positive_clusters),
        official_alert_ids=official_alert_ids,
    )


def assess_cells(
    cells: List[str],
    features_by_cell: Dict[str, CellFeatures],
    reports_by_cell: Dict[str, List[Report]],
    alerts: List[Alert],
    now: datetime,
) -> Dict[str, CellAssessment]:
    """Assess multiple H3 cells in batch, preparing alert geometries and class unions once.
    
    Includes spatial prefiltering over alert union bounding boxes for sub-millisecond evaluation
    across thousands of cells.
    """
    now_utc = _validate_now(now)

    # Parse alert timestamps & geometries once
    prepared_alerts = [AlertGeoPrep(a) for a in alerts]
    hazard_preps = [a for a in prepared_alerts if a.is_hazard]
    clear_preps = [a for a in prepared_alerts if not a.is_hazard]

    hazard_union = unary_union([a.polygon for a in hazard_preps]) if hazard_preps else None
    clear_union = unary_union([a.polygon for a in clear_preps]) if clear_preps else None

    # Spatial bounding prefilter
    hazard_bounds = hazard_union.bounds if hazard_union and not hazard_union.is_empty else None
    clear_bounds = clear_union.bounds if clear_union and not clear_union.is_empty else None

    cell_poly_cache: Dict[str, Polygon] = {}
    assessments: Dict[str, CellAssessment] = {}

    for cell in cells:
        features = features_by_cell.get(cell, CellFeatures())
        reports = reports_by_cell.get(cell, [])

        # 1. Crowd reports clustering
        clusters = cluster_reports(reports, cell, now_utc)
        active_positive_clusters = [c for c in clusters if c.is_active]
        corroborated_positive_clusters = [c for c in clusters if c.is_corroborated]
        has_active_positive = len(active_positive_clusters) > 0

        # 2. Prior & Crowd Logits
        prior_logit = compute_prior_logit(features)
        prior_p = sigmoid(prior_logit)

        raw_crowd_logit = sum(c.decayed_llr for c in clusters)
        clipped_crowd_logit = clamp(raw_crowd_logit, CROWD_LOGIT_MIN, CROWD_LOGIT_MAX)

        posterior_logit = prior_logit + clipped_crowd_logit
        posterior_p = sigmoid(posterior_logit)

        # 3. Geometry & Spatial Prefilter
        if cell not in cell_poly_cache:
            cell_poly_cache[cell] = Polygon(cell_to_polygon_lnglat(cell)[0])
        cell_poly = cell_poly_cache[cell]
        minx, miny, maxx, maxy = cell_poly.bounds

        # Check if cell can possibly intersect alert unions
        may_intersect_hazard = bool(
            hazard_bounds and not (maxx < hazard_bounds[0] or minx > hazard_bounds[2] or maxy < hazard_bounds[1] or miny > hazard_bounds[3])
        )
        may_intersect_clear = bool(
            clear_bounds and not (maxx < clear_bounds[0] or minx > clear_bounds[2] or maxy < clear_bounds[1] or miny > clear_bounds[3])
        )

        override_status = None
        override_p = None
        override_headline = None
        deciding_official: List[AlertGeoPrep] = []
        deciding_sender: Optional[str] = None

        if may_intersect_hazard or may_intersect_clear:
            override_status, override_p, override_headline, deciding_official, deciding_sender = _evaluate_official_override(
                cell_poly,
                hazard_preps if may_intersect_hazard else [],
                clear_preps if may_intersect_clear else [],
                hazard_union if may_intersect_hazard else None,
                clear_union if may_intersect_clear else None,
                has_active_positive,
            )

        # 4. Status Determination
        official_alert_ids: List[str] = []
        if override_status is not None:
            status = override_status
            final_p = override_p
            headline_key = override_headline
            official_alert_ids = [a.alert.id for a in deciding_official]
        else:
            final_p = posterior_p
            if final_p >= LIKELY_P_THRESHOLD and len(corroborated_positive_clusters) >= LIKELY_MIN_CORROBORATED_CLUSTERS:
                status = "likely_hazard"
                headline_key = HEADLINE_AVOID_FLOODED_ROADS
            elif (
                has_active_positive
                and features.rain_available
                and prior_p < CONTRADICTED_PRIOR_P_THRESHOLD
                and len(corroborated_positive_clusters) < LIKELY_MIN_CORROBORATED_CLUSTERS
            ):
                status = "contradicted"
                headline_key = HEADLINE_FOLLOW_OFFICIAL_ONLY
            elif has_active_positive or (not has_active_positive and final_p >= WEATHER_ELEVATED_P_THRESHOLD):
                status = "unverified"
                headline_key = HEADLINE_UNVERIFIED_WARNING
            else:
                status = "clear"
                headline_key = HEADLINE_FOLLOW_OFFICIAL_ONLY

        # 5. Evidence generation
        evidence_items: List[EvidenceItem] = []
        for a in deciding_official:
            evidence_items.append(
                EvidenceItem(
                    type="official",
                    summary=f"Official {a.alert.hazard.replace('_', ' ').title()} Alert from {a.alert.sender}",
                    age_s=max(0, int((now_utc - a.sent_at_dt).total_seconds())),
                    weight=OFFICIAL_EVIDENCE_WEIGHT,
                )
            )

        if features.rain_available:
            r3 = max(0.0, min(features.rain_mm_3h or 0.0, MAX_RAIN_3H_MM))
            r24 = max(0.0, min(features.rain_mm_24h or 0.0, MAX_RAIN_24H_MM))
            fp_note = "; flood-prone area" if features.flood_prone else ""
            rain_weight = (PRIOR_COEFF_RAIN_3H * r3) + (PRIOR_COEFF_RAIN_24H * r24) + (PRIOR_COEFF_FLOOD_PRONE * (1.0 if features.flood_prone else 0.0))
            evidence_items.append(
                EvidenceItem(
                    type="rain",
                    summary=f"Rain {r3:.1f} mm in 3 h, {r24:.1f} mm in 24 h{fp_note}",
                    age_s=0,
                    weight=round(rain_weight, 2),
                )
            )

        for c in clusters:
            if status == "contradicted":
                if override_status == "contradicted" and deciding_sender:
                    summary = f"Claim contradicted by official all-clear from {deciding_sender} ({c.claim}) (unverified)"
                else:
                    summary = "No heavy rain recorded here, so this report is unconfirmed. Follow official guidance."
            else:
                count = len(c.reports)
                if count == 1:
                    summary = f"1 report ({c.claim}) (unverified)"
                else:
                    summary = f"{count} similar reports counted as 1 ({c.claim}) (unverified)"

            evidence_items.append(
                EvidenceItem(
                    type="crowd",
                    summary=summary,
                    age_s=int(c.dt_seconds),
                    weight=round(c.decayed_llr, 2),
                )
            )

        evidence_items.sort(key=lambda e: (EVIDENCE_RANK[e.type], e.age_s, e.summary))

        assessments[cell] = CellAssessment(
            cell=cell,
            status=status,
            p_hazard=round(final_p, 4),
            headline_key=headline_key,
            prior_logit=round(prior_logit, 4),
            crowd_logit_raw=round(raw_crowd_logit, 4),
            crowd_logit_clipped=round(clipped_crowd_logit, 4),
            posterior_logit=round(posterior_logit, 4),
            evidence=evidence_items,
            cluster_count_positive=len(active_positive_clusters),
            official_alert_ids=official_alert_ids,
        )

    return assessments
