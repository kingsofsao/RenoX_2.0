"""FalkorDB connection management for the API, per project.

One FalkorDB client (connection pool) is shared by the project registry and every project's
GraphStore. Routes receive the store of the project named in the URL (`/api/projects/{id}/...`),
and only after checking that the signed-in user owns that project. The project - and so the
graph - is always chosen here on the server, never by the client.

If the database is down at startup or drops later, the next request retries. Error details are
logged server-side; clients only ever see generic messages.
"""

from __future__ import annotations

import logging
import threading
import time

from fastapi import Depends, Request
from falkordb import FalkorDB
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from researchmind.accounts import BaseAccounts, FalkorAccounts, User
from researchmind.config import get_settings
from researchmind.graph import GraphConnectionError, GraphStore
from researchmind.projects import FalkorRegistry, Project

from .auth import get_current_user

log = logging.getLogger("researchmind.api.database")


class DatabaseUnavailable(Exception):
    """Raised to routes when FalkorDB cannot be used; mapped to HTTP 503."""

    def __init__(self, reason: str = "unavailable"):
        super().__init__(reason)
        self.reason = reason  # "not_configured" | "unavailable"


_db: FalkorDB | None = None
_registry: FalkorRegistry | None = None
_accounts: FalkorAccounts | None = None
_stores: dict[str, GraphStore] = {}
_lock = threading.RLock()


def _client() -> FalkorDB:
    global _db
    settings = get_settings()
    if not settings.falkordb_url:
        raise DatabaseUnavailable("not_configured")
    if _db is None:
        try:
            db = FalkorDB.from_url(settings.falkordb_url)
            db.connection.ping()
        except Exception as e:
            log.warning("FalkorDB connection failed: %s", e.__class__.__name__)  # never log the URL
            raise DatabaseUnavailable("unavailable") from e
        _db = db
    return _db


def get_registry() -> FalkorRegistry:
    """The project registry (projects + saved investigations)."""
    global _registry
    if _registry is not None:
        return _registry
    with _lock:
        if _registry is None:
            try:
                reg = FalkorRegistry(_client())
                reg.ensure_default()
                n = reg.mark_interrupted()
                if n:
                    log.info("Marked %d investigation(s) interrupted by the previous shutdown", n)
            except DatabaseUnavailable:
                raise
            except (RedisConnectionError, RedisTimeoutError, OSError) as e:
                log.warning("Registry unavailable: %s", e)
                reset_store()
                raise DatabaseUnavailable("unavailable") from e
            _registry = reg
        return _registry


def get_account_store() -> BaseAccounts:
    """Users and sessions (stored in the registry graph)."""
    global _accounts
    if _accounts is not None:
        return _accounts
    with _lock:
        if _accounts is None:
            try:
                _accounts = FalkorAccounts(_client(), get_registry().graph_name)
            except (RedisConnectionError, RedisTimeoutError, OSError) as e:
                log.warning("Account store unavailable: %s", e.__class__.__name__)
                reset_store()
                raise DatabaseUnavailable("unavailable") from e
        return _accounts


def get_principal(user: User = Depends(get_current_user)) -> str:
    """The acting user's id. Every project, graph and investigation lookup is checked against it."""
    return user.id


def get_project(request: Request, owner: str = Depends(get_principal),
                registry=Depends(get_registry)) -> Project:
    """Project from the URL path (`project_id`), only if the signed-in user owns it (404 otherwise)."""
    return registry.get_project(request.path_params.get("project_id", ""), owner)


def store_for(project: Project) -> GraphStore:
    """Cached GraphStore bound to the project's own graph."""
    store = _stores.get(project.id)
    if store is not None:
        return store
    with _lock:
        store = _stores.get(project.id)
        if store is None:
            try:
                store = GraphStore(graph_name=project.graph_name, db=_client())
            except GraphConnectionError as e:
                log.warning("FalkorDB connection failed: %s", e)
                raise DatabaseUnavailable("unavailable") from e
            _stores[project.id] = store
            log.info("Opened graph for project %s", project.id)
        return store


def get_store(project: Project = Depends(get_project)) -> GraphStore:
    """FastAPI dependency: the GraphStore of the request's project."""
    return store_for(project)


def forget_project(project_id: str) -> None:
    with _lock:
        _stores.pop(project_id, None)


def reset_store() -> None:
    """Drop cached connections so the next request reconnects (after a connection error)."""
    global _db, _registry, _accounts
    with _lock:
        _stores.clear()
        _registry = None
        _accounts = None
        if _db is not None:
            try:
                _db.close()
            except Exception:
                pass
        _db = None


def check_database() -> dict:
    """Connectivity probe for /api/health. Never raises."""
    settings = get_settings()
    if not settings.falkordb_url:
        return {"status": "not_configured", "graph": settings.graph_name, "latency_ms": None,
                "message": "FALKORDB_URL is not set in backend/.env"}
    try:
        db = _client()
        start = time.perf_counter()
        db.connection.ping()
        latency = round((time.perf_counter() - start) * 1000, 1)
        return {"status": "connected", "graph": settings.graph_name, "latency_ms": latency, "message": None}
    except DatabaseUnavailable:
        return {"status": "unavailable", "graph": settings.graph_name, "latency_ms": None,
                "message": "Could not connect to FalkorDB"}
    except (RedisConnectionError, RedisTimeoutError, OSError) as e:
        log.warning("FalkorDB health probe failed: %s", e.__class__.__name__)
        reset_store()
        return {"status": "unavailable", "graph": settings.graph_name, "latency_ms": None,
                "message": "Lost connection to FalkorDB"}
