"""Health endpoints.

GET /api/health/live - public liveness probe for load balancers: {"status": "ok"} and nothing else.
GET /api/health      - signed-in users: backend, database and AI status, without internal URLs,
                       graph names or other configuration details.
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from researchmind import __version__, embeddings
from researchmind.accounts import User
from researchmind.config import get_settings
from researchmind.llm import llm_status

from ..auth import get_current_user
from ..config import get_api_settings
from ..database import check_database
from ..schemas.health import HealthResponse, LLMStatus

router = APIRouter(tags=["health"])
STARTED = time.monotonic()
log = logging.getLogger("researchmind.api.health")
PUBLIC_LLM_FIELDS = ("provider", "model", "status", "reachable", "model_available")
# Users see what the status means for them; the operator-facing detail (URLs, commands) is logged.
USER_MESSAGES = {"ready": "The AI model is ready.", "configured": "The AI service is configured."}
UNAVAILABLE = "The AI service is not available right now, so investigations cannot run. Please contact the administrator."


def _public_llm(refresh: bool = False) -> dict:
    st = llm_status(refresh=refresh)
    if st.get("status") not in USER_MESSAGES:
        log.warning("AI service status %s: %s", st.get("status"), st.get("message"))
    return {**{k: st.get(k) for k in PUBLIC_LLM_FIELDS}, "message": USER_MESSAGES.get(st.get("status"), UNAVAILABLE)}


@router.get("/health/live")
def live() -> dict:
    return {"status": "ok"}


@router.get("/llm/status", response_model=LLMStatus)
def llm_provider_status(refresh: bool = False, _: User = Depends(get_current_user)) -> dict:
    """Whether the AI model is reachable and ready. Cached for 30 s; `?refresh=true` checks again now."""
    return _public_llm(refresh)


@router.get("/health", response_model=HealthResponse)
def health(_: User = Depends(get_current_user)) -> dict:
    """Always 200 while the API process is up; `database.status` says whether the database is usable."""
    api, core = get_api_settings(), get_settings()
    database = check_database()
    embedder = embeddings.get_embedder() if embeddings.is_loaded() else None
    return {
        "status": "ok" if database["status"] == "connected" else "degraded",
        "backend": {"status": "ok", "version": __version__, "uptime_seconds": round(time.monotonic() - STARTED, 1)},
        "database": {"status": database["status"], "latency_ms": database["latency_ms"],
                     "message": None if database["status"] == "connected" else "The database is not reachable right now."},
        "config": {"max_upload_mb": api.max_upload_mb, "max_files_per_upload": api.max_files_per_upload,
                   "llm_configured": core.has_llm, "ai_required": api.ai_required,
                   "embedding_model": embedder.name if embedder else None, "llm": _public_llm()},
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
