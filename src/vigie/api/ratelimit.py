"""Per-token sliding window, kept in memory.

It is a courtesy limit against a runaway client, not the main defence: Traefik limits
by IP in front, and the daily quota in SQLite holds across pods and restarts. A window
per pod is enough for that role and costs no round trip.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

WINDOW_S = 60.0


class SlidingWindowLimiter:
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> int | None:
        """Count one hit. Returns None if allowed, else the seconds to wait."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - WINDOW_S:
                hits.popleft()
            if len(hits) >= self._limit:
                return max(1, math.ceil(hits[0] + WINDOW_S - now))
            hits.append(now)
            return None
