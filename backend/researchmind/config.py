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
    anthropic_timeout_s: float = 120.0
    store_pages_in_graph: bool = True
    # Investigation LLM provider: "ollama" | "anthropic" | "none"; "auto" = anthropic if a key is set, else none
    llm_provider: str = "auto"
    llm_model: str | None = None
    ollama_base_url: str = "http://localhost:11434"
    llm_timeout_s: float = 300.0          # per model request
    llm_max_output_tokens: int = 1024     # report length cap
    llm_context_tokens: int = 8192        # model context window requested from Ollama (num_ctx)
    llm_max_context_chars: int = 9000     # evidence pack size cap sent to the model
    llm_max_tool_rounds: int = 2          # extra evidence searches the model may request
    llm_temperature: float = 0.2

    @property
    def has_anthropic_key(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))

    @property
    def resolved_provider(self) -> str:
        """The provider investigations will use: "ollama", "anthropic" or "none"."""
        p = self.llm_provider
        if p == "auto":
            return "anthropic" if self.has_anthropic_key else "none"
        if p == "anthropic" and not self.has_anthropic_key:
            return "none"
        return p if p in {"ollama", "anthropic"} else "none"

    @property
    def has_llm(self) -> bool:
        """True when an investigation LLM is configured (not necessarily reachable)."""
        return self.resolved_provider != "none"


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
        anthropic_timeout_s=_float("ANTHROPIC_TIMEOUT_SECONDS", 120.0),
        store_pages_in_graph=_bool("STORE_PAGES_IN_GRAPH", True),
        llm_provider=os.getenv("LLM_PROVIDER", "auto").strip().lower() or "auto",
        llm_model=os.getenv("LLM_MODEL", "").strip() or None,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/"),
        llm_timeout_s=_float("LLM_TIMEOUT_SECONDS", 300.0),
        llm_max_output_tokens=int(_float("LLM_MAX_OUTPUT_TOKENS", 1024)),
        llm_context_tokens=int(_float("LLM_CONTEXT_TOKENS", 8192)),
        llm_max_context_chars=int(_float("LLM_MAX_CONTEXT_CHARS", 9000)),
        llm_max_tool_rounds=int(_float("LLM_MAX_TOOL_ROUNDS", 2)),
        llm_temperature=_float("LLM_TEMPERATURE", 0.2),
    )


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default
