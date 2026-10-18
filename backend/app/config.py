"""API settings (environment variables, loaded from backend/.env by researchmind.config)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from researchmind.config import get_settings


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None or not v.strip() else v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ApiSettings:
    allowed_origins: list[str]
    max_upload_mb: int
    max_files_per_upload: int
    upload_dir: Path
    graph_name: str
    falkordb_configured: bool
    investigation_timeout_s: float = 240.0
    investigation_max_concurrent: int = 2
    # --- deployment and security -------------------------------------------------
    environment: str = "development"          # development | production
    cookie_secure: bool = False               # Secure + __Host- cookies (HTTPS only); always on in production
    session_ttl_hours: int = 24 * 7           # absolute session lifetime
    session_idle_hours: int = 24              # sign out after this long without activity
    allow_signup: bool = True
    ai_required: bool = True                  # investigations fail instead of falling back to the offline plan
    investigations_per_user: int = 1          # concurrent investigations per account
    rate_limit_per_minute: int = 240          # all API requests, per client IP
    auth_attempts_per_window: int = 20        # sign-in/sign-up attempts per IP per 15 minutes
    uploads_per_hour: int = 60                # files per account per hour
    investigations_per_hour: int = 30         # investigations started per account per hour
    contact_per_hour: int = 5                 # contact-form messages per IP per hour
    admin_emails: frozenset[str] = frozenset()  # accounts that may see site statistics and contact messages
    origin_secret: str = ""                   # set: only requests from the front proxy (x-origin-secret) are served

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    core = get_settings()
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    environment = "production" if environment in {"prod", "production"} else "development"
    production = environment == "production"
    return ApiSettings(
        allowed_origins=[o.strip().rstrip("/") for o in origins.split(",") if o.strip()],
        max_upload_mb=_int("MAX_UPLOAD_MB", 25),
        max_files_per_upload=_int("MAX_FILES_PER_UPLOAD", 10),
        upload_dir=Path(os.getenv("UPLOAD_DIR", core.data_dir / "uploads")),
        graph_name=core.graph_name,
        falkordb_configured=bool(core.falkordb_url),
        investigation_timeout_s=float(_int("INVESTIGATION_TIMEOUT_SECONDS", 240)),
        investigation_max_concurrent=_int("INVESTIGATION_MAX_CONCURRENT", 2),
        environment=environment,
        cookie_secure=production or _bool("COOKIE_SECURE", False),
        session_ttl_hours=max(1, _int("SESSION_TTL_HOURS", 24 * 7)),
        session_idle_hours=max(1, _int("SESSION_IDLE_HOURS", 24)),
        allow_signup=_bool("ALLOW_SIGNUP", True),
        ai_required=_bool("AI_REQUIRED", True),
        investigations_per_user=max(1, _int("INVESTIGATIONS_PER_USER", 1)),
        rate_limit_per_minute=max(10, _int("RATE_LIMIT_PER_MINUTE", 240)),
        auth_attempts_per_window=max(3, _int("AUTH_ATTEMPTS_PER_WINDOW", 20)),
        uploads_per_hour=max(1, _int("UPLOADS_PER_HOUR", 60)),
        investigations_per_hour=max(1, _int("INVESTIGATIONS_PER_HOUR", 30)),
        contact_per_hour=max(1, _int("CONTACT_PER_HOUR", 5)),
        admin_emails=frozenset(e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()),
        origin_secret=os.getenv("ORIGIN_SECRET", "").strip(),
    )
