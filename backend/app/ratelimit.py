"""In-process sliding-window rate limiting.

The API runs as a single process (investigations and their live progress are held in memory), so
an in-process limiter is exact. Behind a reverse proxy, run uvicorn with `--proxy-headers
--forwarded-allow-ips=<proxy ip>` so `request.client.host` is the real client address.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import Request


class RateLimited(Exception):
    """Mapped to HTTP 429 with a Retry-After header."""

    def __init__(self, retry_after: int, message: str = "Too many requests. Please slow down and try again shortly."):
        super().__init__(message)
        self.retry_after = max(1, int(retry_after))


class SlidingWindow:
    def __init__(self, limit: int, window_s: float, clock=time.monotonic, max_keys: int = 100_000):
        self.limit, self.window_s, self.clock, self.max_keys = limit, window_s, clock, max_keys
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, cost: int = 1) -> None:
        """Record `cost` hits for `key`; raise RateLimited if that exceeds the limit (nothing is recorded then)."""
        now = self.clock()
        with self._lock:
            q = self._hits.get(key)
            if q is None:
                if len(self._hits) >= self.max_keys:
                    self._prune(now)
                q = self._hits[key] = deque()
            while q and q[0] <= now - self.window_s:
                q.popleft()
            if len(q) + cost > self.limit:
                raise RateLimited(q[0] + self.window_s - now if q else self.window_s)
            q.extend([now] * cost)

    def _prune(self, now: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or q[-1] <= now - self.window_s]:
            del self._hits[k]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class Limiters:
    """All limiters of the API, built from settings once."""

    def __init__(self, settings):
        self.api = SlidingWindow(settings.rate_limit_per_minute, 60)
        self.auth = SlidingWindow(settings.auth_attempts_per_window, 15 * 60)
        self.uploads = SlidingWindow(settings.uploads_per_hour, 3600)
        self.investigations = SlidingWindow(settings.investigations_per_hour, 3600)

    def reset(self) -> None:
        for lim in (self.api, self.auth, self.uploads, self.investigations):
            lim.reset()


_limiters: Limiters | None = None
_lock = threading.Lock()


def get_limiters() -> Limiters:
    global _limiters
    with _lock:
        if _limiters is None:
            from .config import get_api_settings
            _limiters = Limiters(get_api_settings())
        return _limiters
