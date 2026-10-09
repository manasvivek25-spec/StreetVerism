"""Data types and Pydantic models for the Bayesian Trust Engine."""

from datetime import datetime, timezone
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from backend.app.models.cell import CellStatus
from backend.app.models.state import EvidenceItem


class CellFeatures(BaseModel):
    """Hydrological and meteorological features of an H3 cell."""
    rain_mm_3h: Optional[float] = Field(default=0.0, description="Rainfall accumulation in past 3 hours (mm)")
    rain_mm_24h: Optional[float] = Field(default=0.0, description="Rainfall accumulation in past 24 hours (mm)")
    flood_prone: bool = Field(default=False, description="Whether the cell terrain is topographically flood-prone")
    rain_available: bool = Field(default=True, description="False if rain gauge/radar data is missing or stale")


class Report(BaseModel):
    """Ground-truth crowd report submitted by tourist or local resident."""
    id: str = Field(..., description="Unique report identifier")
    device_id: str = Field(..., description="Anonymized device hardware identifier")
    cell: str = Field(..., description="H3 index string at resolution 8")
    claim: Literal["flooded", "blocked", "safe"] = Field(..., description="Hazard observation claim")
    text: Optional[str] = Field(default=None, description="Optional textual description of conditions")
    created_at: datetime = Field(..., description="Timezone-aware UTC timestamp of report creation")
    tier: Literal["default", "verified_local"] = Field(
        default="default", description="Reliability tier of the reporter"
    )

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_tz_aware_datetime(cls, v: Any) -> datetime:
        """Parse ISO string and strictly enforce timezone-awareness."""
        if isinstance(v, str):
            clean = v.strip()
            if clean.endswith("Z") or clean.endswith("z"):
                clean = clean[:-1] + "+00:00"
            dt = datetime.fromisoformat(clean)
        elif isinstance(v, datetime):
            dt = v
        else:
            raise ValueError(f"Invalid created_at datetime: {v}")

        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            raise ValueError("Report.created_at must be a timezone-aware datetime.")
        return dt.astimezone(timezone.utc)


class CellAssessment(BaseModel):
    """Complete explainable Bayesian risk evaluation for an H3 cell."""
    cell: str = Field(..., description="Evaluated H3 resolution-8 cell")
    status: CellStatus = Field(..., description="Deterministic crisis status")
    p_hazard: float = Field(..., ge=0.0, le=1.0, description="Posterior probability of acute hazard")
    headline_key: str = Field(..., description="Canonical instruction/status template key")
    prior_logit: float = Field(..., description="Logit hazard prior based on rain and terrain")
    crowd_logit_raw: float = Field(..., description="Unbounded raw sum of decayed crowd report LLRs")
    crowd_logit_clipped: float = Field(..., description="Crowd logit clamped to [-3.0, +3.0]")
    posterior_logit: float = Field(..., description="Final posterior log-odds before sigmoid mapping")
    evidence: List[EvidenceItem] = Field(
        default_factory=list, description="Deterministic explainable evidence breakdown for Why UI"
    )
    cluster_count_positive: int = Field(
        default=0, description="Number of active positive (flooded/blocked) report clusters"
    )
    official_alert_ids: List[str] = Field(
        default_factory=list, description="IDs of official alerts covering the cell"
    )
