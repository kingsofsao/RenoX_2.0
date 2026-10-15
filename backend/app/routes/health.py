"""GET /api/health - backend liveness plus FalkorDB connectivity, reported separately."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter

from researchmind import __version__, embeddings
from researchmind.config import get_settings
from researchmind.llm import llm_status

from ..config import get_api_settings
from ..database import check_database
from ..schemas.health import HealthResponse, LLMStatus

router = APIRouter(tags=["health"])
STARTED = time.monotonic()


@router.get("/llm/status", response_model=LLMStatus)
def llm_provider_status(refresh: bool = False) -> dict:
    """Whether the configured investigation LLM provider is reachable and its model installed. No secrets.
    Cached for 30 s; `?refresh=true` checks again now."""
    return llm_status(refresh=refresh)


@router.get("/health", response_model=HealthResponse)
def health() -> dict:
    """Always 200 while the API process is up; `database.status` says whether FalkorDB is usable."""
    api, core = get_api_settings(), get_settings()
    database = check_database()
    # Report the embedder only once it has been loaded (startup preloads it in the background).
    embedder = embeddings.get_embedder() if embeddings.is_loaded() else None
    return {
        "status": "ok" if database["status"] == "connected" else "degraded",
        "backend": {"status": "ok", "version": __version__, "uptime_seconds": round(time.monotonic() - STARTED, 1)},
        "database": database,
        "config": {"max_upload_mb": api.max_upload_mb, "max_files_per_upload": api.max_files_per_upload,
                   "llm_configured": core.has_llm, "embedding_model": embedder.name if embedder else None,
                   "llm": llm_status()},
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
