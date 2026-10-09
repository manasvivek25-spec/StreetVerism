"""Scenario playback models for StreetVerism."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator


class ScenarioStart(BaseModel):
    """Payload to launch historical scenario replay."""
    name: str = Field(..., description="Scenario identifier, e.g. michaung_replay")
    speed: float = Field(default=1.0, gt=0.0, le=60.0, description="Playback speed multiplier")


class ScenarioSeek(BaseModel):
    """Payload to jump the scenario clock."""
    t: Optional[str] = Field(default=None, description="Target ISO-8601 UTC timestamp")
    offset_s: Optional[int] = Field(default=None, description="Offset seconds from scenario start")

    @model_validator(mode="after")
    def validate_exactly_one_field(self) -> "ScenarioSeek":
        has_t = self.t is not None
        has_offset = self.offset_s is not None
        if (has_t and has_offset) or (not has_t and not has_offset):
            raise ValueError("Payload must contain exactly one of 't' or 'offset_s'")
        return self


class ScenarioStatus(BaseModel):
    """Current state of replay engine and clock."""
    name: str = Field(..., description="Active scenario name or 'live'")
    mode: Literal["live", "replay"] = Field(..., description="Operating mode")
    is_running: bool = Field(..., description="Whether scenario is currently playing")
    paused: bool = Field(default=False, description="Whether playback is paused")
    speed: float = Field(default=1.0, description="Clock multiplier")
    current_time: str = Field(..., description="Effective current time (ISO-8601 UTC)")
    elapsed_s: int = Field(default=0, description="Elapsed seconds since scenario start")
    scenario_start: Optional[str] = Field(default=None, description="Start timestamp of scenario")
    scenario_end: Optional[str] = Field(default=None, description="End timestamp of scenario")
    is_replay: bool = Field(..., description="True if operating in replay mode")


class ScenarioResetResponse(BaseModel):
    """Response returned upon resetting to live mode."""
    ok: bool = True
    mode: str = "live"
    is_replay: bool = False
