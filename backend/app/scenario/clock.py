"""Thread-safe scenario replay clock with injectable wall time and speed scaling."""

import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Union

from backend.app.scenario.replay import ReplayOverlay
from backend.app.scenario.types import Scenario


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScenarioClock:
    """Thread-safe replay clock for simulated scenario playback.
    
    Guarantees:
    - Injectable wall_clock callable for deterministic testing.
    - speed in [0, 3600] (0 = paused, invalid speed raises ValueError).
    - start(speed): resumes from current sim time; if finished, restarts from t0. Clears overlay.
    - seek(t=None, offset_s=None): strict XOR rule (exactly one required, else ValueError). Clamped to [t0, t_end].
      Re-anchors wall time if running. Does NOT clear overlay.
    - reset(): resets to t0, speed 0, paused. Clears overlay.
    - sim_time(): anchor_sim + (wall_now - anchor_wall) * speed, clamped to [t0, t_end].
    - Thread-safe using threading.Lock.
    """

    MIN_SPEED: float = 0.0
    MAX_SPEED: float = 3600.0

    def __init__(
        self,
        scenario: Scenario,
        wall_clock: Optional[Callable[[], datetime]] = None,
        overlay: Optional[ReplayOverlay] = None,
    ) -> None:
        self.scenario = scenario
        self.wall_clock = wall_clock or _utc_now
        self.overlay = overlay

        self.t0: datetime = self._ensure_utc(scenario.t0)
        self.duration_s: int = int(scenario.duration_s)
        self.t_end: datetime = self.t0 + timedelta(seconds=self.duration_s)

        self._lock = threading.Lock()
        self._speed: float = 0.0
        self._anchor_sim: datetime = self.t0
        self._anchor_wall: datetime = self._now_wall()

    def _ensure_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _now_wall(self) -> datetime:
        return self._ensure_utc(self.wall_clock())

    def start(self, speed: float = 1.0) -> None:
        """Start or resume playback at given speed in [0, 3600]. Clears overlay."""
        if not (self.MIN_SPEED <= speed <= self.MAX_SPEED):
            raise ValueError(
                f"Clock speed {speed} is invalid. Speed must be within [{self.MIN_SPEED}, {self.MAX_SPEED}]."
            )

        with self._lock:
            wall_now = self._now_wall()
            current = self._compute_sim_time_locked(wall_now)

            # If finished, restart from t0
            if current >= self.t_end:
                current = self.t0

            self._anchor_sim = current
            self._anchor_wall = wall_now
            self._speed = float(speed)

            # start clears overlay
            if self.overlay is not None:
                self.overlay.clear()

    def seek(
        self,
        t: Optional[datetime] = None,
        offset_s: Optional[Union[int, float]] = None,
    ) -> datetime:
        """Seek to simulated time or offset. Strict XOR rule: exactly one required.
        
        Does NOT clear overlay.
        """
        # Strict XOR check
        has_t = t is not None
        has_offset = offset_s is not None
        if has_t == has_offset:
            raise ValueError("Exactly one of 't' or 'offset_s' must be provided for seek.")

        with self._lock:
            if has_t:
                target = self._ensure_utc(t)
            else:
                target = self.t0 + timedelta(seconds=float(offset_s))

            # Clamp to [t0, t_end]
            if target < self.t0:
                target = self.t0
            elif target > self.t_end:
                target = self.t_end

            wall_now = self._now_wall()
            self._anchor_sim = target
            self._anchor_wall = wall_now

            # Note: seek NEVER clears overlay
            return target

    def reset(self) -> None:
        """Reset playback to scenario start, paused. Clears overlay."""
        with self._lock:
            self._anchor_sim = self.t0
            self._anchor_wall = self._now_wall()
            self._speed = 0.0

            if self.overlay is not None:
                self.overlay.clear()

    def pause(self) -> None:
        """Pause playback, preserving current sim time."""
        with self._lock:
            wall_now = self._now_wall()
            self._anchor_sim = self._compute_sim_time_locked(wall_now)
            self._anchor_wall = wall_now
            self._speed = 0.0

    def sim_time(self) -> datetime:
        """Get current simulated time, clamped to [t0, t_end]."""
        with self._lock:
            return self._compute_sim_time_locked(self._now_wall())

    def _compute_sim_time_locked(self, wall_now: datetime) -> datetime:
        if self._speed == 0.0:
            current = self._anchor_sim
        else:
            elapsed_wall_s = (wall_now - self._anchor_wall).total_seconds()
            current = self._anchor_sim + timedelta(seconds=elapsed_wall_s * self._speed)

        # Clamp
        if current < self.t0:
            return self.t0
        if current > self.t_end:
            return self.t_end
        return current

    def status(self) -> Dict[str, Any]:
        """Report clock status for API or monitoring."""
        with self._lock:
            wall_now = self._now_wall()
            current = self._compute_sim_time_locked(wall_now)
            elapsed = int((current - self.t0).total_seconds())
            finished = current >= self.t_end

            return {
                "name": self.scenario.name,
                "label": self.scenario.label,
                "disclaimer": self.scenario.disclaimer,
                "mode": "replay",
                "is_running": (self._speed > 0.0 and not finished),
                "paused": (self._speed == 0.0),
                "speed": self._speed,
                "current_time": current.isoformat(),
                "elapsed_s": elapsed,
                "scenario_start": self.t0.isoformat(),
                "scenario_end": self.t_end.isoformat(),
                "duration_s": self.duration_s,
                "is_replay": True,
                "finished": finished,
            }
