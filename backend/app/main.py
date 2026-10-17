"""ResearchMind AI - FastAPI application.

Run from the backend folder:
    development:  uvicorn app.main:app --reload --port 8000
    production:   ENVIRONMENT=production uvicorn app.main:app --host 0.0.0.0 --port 8000 \
                  --proxy-headers --forwarded-allow-ips=<reverse proxy ip> --no-server-header
Run a single process: investigations and their live progress are held in memory.
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
from researchmind.projects import ProjectError

from .auth import AuthRequired, clear_session_cookie
from .config import get_api_settings
from .database import DatabaseUnavailable, reset_store
from .middleware import SecurityMiddleware
from .ratelimit import RateLimited
from .routes import auth, graph, health, investigations, papers, projects

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("researchmind.api")


def _warm_embedder() -> None:
    """Load the embedding model in the background so the first upload is not slow."""
    try:
        from researchmind.embeddings import get_embedder
        log.info("Embedding model ready: %s", get_embedder().name)
    except Exception as e:  # never block startup on this
        log.warning("Embedding model preload failed: %s", e)


def _check_deployment(settings) -> None:
    if not settings.is_production:
        log.warning("Running in DEVELOPMENT mode (cookies without Secure, API docs at /docs). "
                    "Set ENVIRONMENT=production when deploying.")
        return
    insecure = [o for o in settings.allowed_origins if o.startswith("http://")]
    if insecure:
        log.error("ALLOWED_ORIGINS contains non-HTTPS origins in production: %s", insecure)
    if not settings.falkordb_configured:
        log.error("FALKORDB_URL is not set: sign-in and all data routes will fail.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_api_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    _check_deployment(settings)
    threading.Thread(target=_warm_embedder, daemon=True).start()
    log.info("ResearchMind API starting (%s, FalkorDB %s, CORS origins %s)", settings.environment,
             "configured" if settings.falkordb_configured else "NOT configured", settings.allowed_origins)
    yield
    reset_store()


_settings = get_api_settings()
app = FastAPI(title="ResearchMind AI API", version=__version__, lifespan=lifespan,
              # Interactive docs only in development: they map the whole API surface.
              docs_url=None if _settings.is_production else "/docs",
              redoc_url=None, openapi_url=None if _settings.is_production else "/openapi.json")
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
    max_age=600,
)


def _error(status: int, message: str, code: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}}, headers=headers)


@app.exception_handler(AuthRequired)
async def auth_required(_: Request, exc: AuthRequired):
    resp = _error(401, "Please sign in to continue.", "auth_required")
    clear_session_cookie(resp)
    return resp


@app.exception_handler(RateLimited)
async def rate_limited(_: Request, exc: RateLimited):
    return _error(429, str(exc), "rate_limited", {"Retry-After": str(exc.retry_after)})


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable(_: Request, exc: DatabaseUnavailable):
    if exc.reason == "not_configured":
        log.error("FALKORDB_URL is not configured")
    return _error(503, "The service is temporarily unavailable. Please try again shortly.", "database_unavailable")


@app.exception_handler(RedisConnectionError)
@app.exception_handler(RedisTimeoutError)
async def database_dropped(_: Request, exc: Exception):
    log.warning("FalkorDB connection error during request: %s", exc.__class__.__name__)
    reset_store()
    return _error(503, "Lost connection to the database. Please retry.", "database_unavailable")


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    return _error(exc.status_code, str(exc.detail), "http_error")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", []) if p not in ("body", "query", "path"))
    detail = f" ({where})" if where else ""
    # Never echo the submitted value back (it may be a password).
    return _error(422, f"Invalid request{detail}: {first.get('msg', 'validation failed')}", "validation_error")


@app.exception_handler(ProjectError)
async def project_error(_: Request, exc: ProjectError):
    status = {"not_found": 404, "invalid": 422, "conflict": 409, "forbidden": 403}.get(exc.code, 400)
    return _error(status, str(exc), f"project_{exc.code}")


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error")  # the traceback stays in server logs only
    return _error(500, "An internal error occurred. Please try again.", "internal_error")


app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
# Project-scoped data routes. The project (and so the FalkorDB graph and data folder) comes from the
# URL and is resolved on the server by database.get_project, only for the project's owner.
for _router in (papers.router, graph.router, investigations.router):
    app.include_router(_router, prefix="/api/projects/{project_id}")


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"name": "ResearchMind AI API"}
