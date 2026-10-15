"""ResearchMind AI - FastAPI application.

Run from the backend folder:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

from researchmind import __version__

from .config import get_api_settings
from .database import DatabaseUnavailable, reset_store
from .routes import graph, health, papers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("researchmind.api")


def _warm_embedder() -> None:
    """Load the embedding model in the background so the first upload is not slow."""
    try:
        from researchmind.embeddings import get_embedder
        log.info("Embedding model ready: %s", get_embedder().name)
    except Exception as e:  # never block startup on this
        log.warning("Embedding model preload failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_api_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_warm_embedder, daemon=True).start()
    log.info("ResearchMind API starting (graph '%s', FalkorDB %s, CORS origins %s)", settings.graph_name,
             "configured" if settings.falkordb_configured else "NOT configured", settings.allowed_origins)
    yield
    reset_store()


app = FastAPI(title="ResearchMind AI API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_api_settings().allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


def _error(status: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable(_: Request, exc: DatabaseUnavailable):
    if exc.reason == "not_configured":
        return _error(503, "The graph database is not configured. Set FALKORDB_URL in backend/.env.",
                      "database_not_configured")
    return _error(503, "The graph database is currently unavailable. Please try again shortly.", "database_unavailable")


@app.exception_handler(RedisConnectionError)
@app.exception_handler(RedisTimeoutError)
async def database_dropped(_: Request, exc: Exception):
    log.warning("FalkorDB connection error during request: %s", exc)
    reset_store()
    return _error(503, "Lost connection to the graph database. Please retry.", "database_unavailable")


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, str(exc.detail), "http_error")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
    detail = f" ({where})" if where else ""
    return _error(422, f"Invalid request{detail}: {first.get('msg', 'validation failed')}", "validation_error")


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error")  # the traceback stays in server logs only
    return _error(500, "An internal error occurred. Check the server logs for details.", "internal_error")


app.include_router(health.router, prefix="/api")
app.include_router(papers.router, prefix="/api")
app.include_router(graph.router, prefix="/api")


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": "ResearchMind AI API", "docs": "/docs", "health": "/api/health"}
