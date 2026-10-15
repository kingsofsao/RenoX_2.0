"""Settings loaded from environment variables (and a local .env file)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent   # researchmind-ai/backend
REPO_ROOT = BACKEND_ROOT.parent                          # researchmind-ai
PROJECT_ROOT = BACKEND_ROOT  # kept for older imports
# backend/.env is the canonical location; a repo-root .env is also honoured. Real env vars win.
load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(REPO_ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    falkordb_url: str | None
    graph_name: str
    anthropic_model: str
    use_llm_extraction: bool
    refusal_fallback: bool
    embedding_backend: str  # "auto" | "sentence-transformers" | "hashing"
    embedding_model: str
    data_dir: Path

    @property
    def has_llm(self) -> bool:
        """True when Anthropic credentials appear to be configured."""
        return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def get_settings() -> Settings:
    data_dir = Path(os.getenv("RESEARCHMIND_DATA_DIR", REPO_ROOT / "data"))
    return Settings(
        falkordb_url=os.getenv("FALKORDB_URL") or None,
        graph_name=os.getenv("FALKORDB_GRAPH", "researchmind"),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5"),
        use_llm_extraction=_bool("USE_LLM_EXTRACTION", True),
        refusal_fallback=_bool("CLAUDE_REFUSAL_FALLBACK", True),
        embedding_backend=os.getenv("EMBEDDING_BACKEND", "auto").lower(),
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        data_dir=data_dir,
    )
