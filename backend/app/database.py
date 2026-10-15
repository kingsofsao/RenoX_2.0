"""FalkorDB connection management for the API.

One GraphStore is shared across requests (the underlying redis client pools connections and
is thread-safe). If the database is down at startup or drops later, the next request retries.
Error details are logged server-side; clients only ever see generic messages.
"""

from __future__ import annotations

import logging
import threading
import time

from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from researchmind.config import get_settings
from researchmind.graph import GraphConnectionError, GraphStore

log = logging.getLogger("researchmind.api.database")


class DatabaseUnavailable(Exception):
    """Raised to routes when FalkorDB cannot be used; mapped to HTTP 503."""

    def __init__(self, reason: str = "unavailable"):
        super().__init__(reason)
        self.reason = reason  # "not_configured" | "unavailable"


_store: GraphStore | None = None
_lock = threading.Lock()


def _connect() -> GraphStore:
    settings = get_settings()
    if not settings.falkordb_url:
        raise DatabaseUnavailable("not_configured")
    try:
        store = GraphStore()
    except GraphConnectionError as e:
        log.warning("FalkorDB connection failed: %s", e)  # message never contains the password
        raise DatabaseUnavailable("unavailable") from e
    log.info("Connected to FalkorDB graph '%s'", store.graph_name)
    return store


def get_store() -> GraphStore:
    """FastAPI dependency: the shared GraphStore, connecting lazily."""
    global _store
    if _store is not None:
        return _store
    with _lock:
        if _store is None:
            _store = _connect()
        return _store


def reset_store() -> None:
    """Drop the cached connection so the next request reconnects (after a connection error)."""
    global _store
    with _lock:
        if _store is not None:
            _store.close()
        _store = None


def check_database() -> dict:
    """Connectivity probe for /api/health. Never raises."""
    settings = get_settings()
    if not settings.falkordb_url:
        return {"status": "not_configured", "graph": settings.graph_name, "latency_ms": None,
                "message": "FALKORDB_URL is not set in backend/.env"}
    try:
        store = get_store()
        start = time.perf_counter()
        store.query("RETURN 1", read_only=True)
        latency = round((time.perf_counter() - start) * 1000, 1)
        return {"status": "connected", "graph": store.graph_name, "latency_ms": latency, "message": None}
    except DatabaseUnavailable:
        return {"status": "unavailable", "graph": settings.graph_name, "latency_ms": None,
                "message": "Could not connect to FalkorDB"}
    except (RedisConnectionError, RedisTimeoutError, OSError) as e:
        log.warning("FalkorDB health probe failed: %s", e)
        reset_store()
        return {"status": "unavailable", "graph": settings.graph_name, "latency_ms": None,
                "message": "Lost connection to FalkorDB"}
