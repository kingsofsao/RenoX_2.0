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

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_api_settings() -> ApiSettings:
    core = get_settings()
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return ApiSettings(
        allowed_origins=[o.strip().rstrip("/") for o in origins.split(",") if o.strip()],
        max_upload_mb=_int("MAX_UPLOAD_MB", 25),
        max_files_per_upload=_int("MAX_FILES_PER_UPLOAD", 10),
        upload_dir=Path(os.getenv("UPLOAD_DIR", core.data_dir / "uploads")),
        graph_name=core.graph_name,
        falkordb_configured=bool(core.falkordb_url),
        investigation_timeout_s=float(_int("INVESTIGATION_TIMEOUT_SECONDS", 240)),
        investigation_max_concurrent=_int("INVESTIGATION_MAX_CONCURRENT", 2),
    )
