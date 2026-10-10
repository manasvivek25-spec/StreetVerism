"""In-memory quota management and token bucket rate limiting for routing providers."""

from datetime import datetime, timezone
import os
import threading
import time
from typing import Optional


class RoutingQuotaManager:
    """Manages provider rate limits (tokens/min) and daily request budgets."""

    def __init__(
        self,
        rate_per_min: Optional[int] = None,
        daily_budget: Optional[int] = None,
    ) -> None:
        self.rate_per_min = rate_per_min or int(os.getenv("ROUTING_PER_MIN", "30"))
        self.daily_budget = daily_budget or int(os.getenv("ROUTING_DAILY_BUDGET", "1500"))

        self._lock = threading.Lock()
        self._tokens = float(self.rate_per_min)
        self._last_refill = time.time()
        self._current_day = self._today_utc()
        self._day_count = 0

    @staticmethod
    def _today_utc() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def acquire(self) -> bool:
        """Attempt to consume 1 provider quota token. Returns True if granted, False if exceeded."""
        with self._lock:
            now = time.time()
            today = self._today_utc()

            # 1. Reset daily budget if day rolled over
            if today != self._current_day:
                self._current_day = today
                self._day_count = 0

            # 2. Check daily budget
            if self._day_count >= self.daily_budget:
                return False

            # 3. Refill token bucket based on elapsed time
            elapsed = now - self._last_refill
            refill_rate = self.rate_per_min / 60.0  # tokens per second
            self._tokens = min(float(self.rate_per_min), self._tokens + elapsed * refill_rate)
            self._last_refill = now

            # 4. Check minute token bucket
            if self._tokens < 1.0:
                return False

            # 5. Consume token
            self._tokens -= 1.0
            self._day_count += 1
            return True

    def get_remaining_daily(self) -> int:
        """Return remaining daily requests budget."""
        with self._lock:
            today = self._today_utc()
            if today != self._current_day:
                return self.daily_budget
            return max(0, self.daily_budget - self._day_count)

    def reset(self) -> None:
        """Reset quota counters (used in testing)."""
        with self._lock:
            self._tokens = float(self.rate_per_min)
            self._last_refill = time.time()
            self._day_count = 0
            self._current_day = self._today_utc()
