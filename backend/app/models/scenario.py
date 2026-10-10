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
    bookmark: Optional[str] = Field(default=None, description="Optional named scenario bookmark")

    @model_validator(mode="after")
    def validate_exactly_one_field(self) -> "ScenarioSeek":
        count = sum(x is not None for x in (self.t, self.offset_s, self.bookmark))
        if count != 1:
            raise ValueError("Payload must contain exactly one of 't', 'offset_s', or 'bookmark'")
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
    label: Optional[str] = Field(default=None, description="Replay label banner text")
    disclaimer: Optional[str] = Field(default=None, description="Replay disclaimer disclosure text")
    start_time: Optional[str] = Field(default=None, description="Scenario start time (ISO-8601 UTC)")
    end_time: Optional[str] = Field(default=None, description="Scenario end time (ISO-8601 UTC)")
    duration_s: Optional[int] = Field(default=None, description="Scenario total duration in seconds")
    finished: bool = Field(default=False, description="Whether replay clock reached scenario end")
    bookmarks: Optional[list] = Field(default=None, description="List of scenario narrative bookmarks")


class ScenarioResetResponse(BaseModel):
    """Response returned upon resetting to live mode."""
    ok: bool = True
    mode: str = "live"
    is_replay: bool = False
