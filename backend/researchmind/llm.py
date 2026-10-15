"""LLM providers used by the extractor and the investigation agent.

Providers
  anthropic  ClaudeLLM.create(**messages_api_kwargs)   - Claude tool-use loop (agent._run_claude) + LLM extraction
  ollama     OllamaLLM.chat(messages, tools)           - local model via the Ollama REST API (agent._run_grounded)

Select with LLM_PROVIDER / LLM_MODEL (see config.py). Adding a provider means implementing `chat()`
(and `status()`) like OllamaLLM; the grounded agent only depends on that interface.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Callable

import anthropic
import httpx

from .config import get_settings

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(Exception):
    """The provider cannot serve this request. `code` is safe to show to users."""

    def __init__(self, message: str, code: str = "unavailable"):
        super().__init__(message)
        self.code = code  # unreachable | model_missing | timeout | malformed | http_error | not_configured


class ClaudeLLM:
    provider = "anthropic"

    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.anthropic_model
        # Bounded per-request timeout so a stalled call cannot hold an investigation indefinitely.
        self.client = anthropic.Anthropic(max_retries=3, timeout=settings.anthropic_timeout_s)
        # Server-side refusal fallback: if a safety classifier declines a benign request,
        # the API re-runs it on Anthropic's recommended fallback model instead of failing.
        self.use_fallback = settings.refusal_fallback

    def create(self, **kwargs):
        kwargs.setdefault("model", self.model)
        if self.use_fallback:
            try:
                return self.client.beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
            except anthropic.BadRequestError as e:
                if "fallback" not in str(e).lower():
                    raise
                log.warning("Refusal fallback not accepted (%s); continuing without it.", e)
                self.use_fallback = False
        return self.client.messages.create(**kwargs)

    def status(self) -> dict:
        # No network call: checking would spend tokens. Configured = key present.
        return {"provider": self.provider, "model": self.model, "status": "configured",
                "reachable": None, "model_available": None,
                "message": "Anthropic API key configured (not contacted by the status check)."}


@dataclass
class ChatResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)   # [{"name": str, "arguments": dict}]
    done_reason: str = "stop"                              # stop | length | tool_calls
    eval_tokens: int = 0
    seconds: float = 0.0


_THINK = re.compile(r"<think>.*?</think>", re.S)


class OllamaLLM:
    """Local models through Ollama's /api/chat (streaming, so progress can be reported)."""

    provider = "ollama"

    def __init__(self, model: str | None = None, base_url: str | None = None, timeout_s: float | None = None,
                 transport: httpx.BaseTransport | None = None):
        s = get_settings()
        self.model = model or s.llm_model
        self.base_url = (base_url or s.ollama_base_url).rstrip("/")
        self.timeout_s = timeout_s or s.llm_timeout_s
        self.options = {"num_ctx": s.llm_context_tokens, "num_predict": s.llm_max_output_tokens,
                        "temperature": s.llm_temperature}
        self._transport = transport  # tests inject httpx.MockTransport

    def _client(self, timeout: float) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(timeout, connect=5.0), transport=self._transport)

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        out = {"provider": self.provider, "model": self.model, "base_url": self.base_url,
               "reachable": False, "model_available": False, "installed_models": [], "status": "unreachable", "message": ""}
        if not self.model:
            out.update(status="not_configured", message="LLM_MODEL is not set in backend/.env.")
            return out
        try:
            with self._client(8.0) as c:  # generous: Ollama answers slowly while a model is loading
                tags = c.get("/api/tags").json().get("models", [])
            version = None
        except (httpx.HTTPError, ValueError) as e:
            out["message"] = f"Ollama is not reachable at {self.base_url}. Start the Ollama app (or run `ollama serve`)."
            log.info("Ollama status check failed: %s", e)
            return out
        names = [m.get("name", "") for m in tags]
        out.update(reachable=True, installed_models=names, version=version)
        if _model_installed(self.model, names):
            out.update(model_available=True, status="ready", message=f"Ollama is running with {self.model}.")
        else:
            out.update(status="model_missing", message=f"Model '{self.model}' is not installed. Run: ollama pull {self.model}")
        return out

    # ------------------------------------------------------------------ chat
    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             on_progress: Callable[[int], None] | None = None) -> ChatResult:
        if not self.model:
            raise LLMUnavailable("LLM_MODEL is not set.", "not_configured")
        body = {"model": self.model, "messages": messages, "stream": True, "options": self.options, "keep_alive": "10m"}
        if tools:
            body["tools"] = tools
        text, calls, reason, tokens = [], [], "stop", 0
        t0 = time.monotonic()
        try:
            with self._client(self.timeout_s) as c, c.stream("POST", "/api/chat", json=body) as r:
                if r.status_code == 404:
                    r.read()
                    raise LLMUnavailable(f"Model '{self.model}' is not installed in Ollama. Run: ollama pull {self.model}", "model_missing")
                if r.status_code >= 400:
                    r.read()
                    raise LLMUnavailable(f"Ollama returned HTTP {r.status_code}: {_error_text(r)}", "http_error")
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError as e:
                        raise LLMUnavailable("Ollama returned a malformed response.", "malformed") from e
                    if chunk.get("error"):
                        raise LLMUnavailable(f"Ollama error: {chunk['error']}", "http_error")
                    msg = chunk.get("message") or {}
                    if msg.get("content"):
                        text.append(msg["content"])
                        tokens += 1
                        if on_progress and tokens % 40 == 0:
                            on_progress(tokens)
                    for tc in msg.get("tool_calls") or []:
                        fn = tc.get("function") or {}
                        args = fn.get("arguments")
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        calls.append({"name": fn.get("name", ""), "arguments": args if isinstance(args, dict) else {}})
                    if chunk.get("done"):
                        reason = chunk.get("done_reason") or "stop"
                        tokens = chunk.get("eval_count") or tokens
        except httpx.ConnectError as e:
            raise LLMUnavailable(f"Ollama is not reachable at {self.base_url}.", "unreachable") from e
        except httpx.TimeoutException as e:
            raise LLMUnavailable(f"The model did not answer within {self.timeout_s:.0f} s.", "timeout") from e
        except httpx.HTTPError as e:
            raise LLMUnavailable(f"Ollama request failed ({e.__class__.__name__}).", "http_error") from e
        content = _THINK.sub("", "".join(text)).strip()
        if calls:
            reason = "tool_calls"
        return ChatResult(text=content, tool_calls=calls, done_reason=reason, eval_tokens=tokens,
                          seconds=round(time.monotonic() - t0, 1))


def _model_installed(model: str, names: list[str]) -> bool:
    want = model if ":" in model else f"{model}:latest"
    return any(n == model or n == want for n in names)


def _error_text(r: httpx.Response) -> str:
    try:
        return str(r.json().get("error", ""))[:200]
    except ValueError:
        return r.text[:200]


# ---------------------------------------------------------------------- factories

def get_llm():
    """The investigation LLM for the configured provider, or None (offline mode)."""
    s = get_settings()
    provider = s.resolved_provider
    if provider == "anthropic":
        return ClaudeLLM(s.llm_model or None)
    if provider == "ollama":
        return OllamaLLM()
    return None


def get_extraction_llm() -> ClaudeLLM | None:
    """LLM for knowledge extraction at upload time. Only Claude is supported; otherwise the heuristic extractor runs."""
    return ClaudeLLM() if get_settings().has_anthropic_key else None


_status_cache: tuple[float, tuple, dict] | None = None
STATUS_TTL_S = 30.0


def llm_status(refresh: bool = False) -> dict:
    """Provider status for /api/health and /api/llm/status. Never raises and never includes secrets.

    Cached for STATUS_TTL_S so frequent health polls do not hit the provider (Ollama answers slowly
    while it is generating); `refresh=True` forces a fresh check."""
    global _status_cache
    s = get_settings()
    key = (s.llm_provider, s.resolved_provider, s.llm_model, s.ollama_base_url)
    now = time.monotonic()
    if not refresh and _status_cache and _status_cache[1] == key and now - _status_cache[0] < STATUS_TTL_S:
        return dict(_status_cache[2])
    st = _fresh_status(s)
    _status_cache = (now, key, st)
    return dict(st)


def _fresh_status(s) -> dict:
    provider = s.resolved_provider
    if provider == "none":
        hint = ("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set." if s.llm_provider == "anthropic"
                else "No LLM configured: investigations use the offline plan. Set LLM_PROVIDER and LLM_MODEL in backend/.env.")
        return {"provider": "none", "model": None, "status": "not_configured", "reachable": None,
                "model_available": None, "message": hint}
    try:
        return get_llm().status()
    except Exception as e:  # never break health checks
        log.warning("LLM status check failed: %s", e)
        return {"provider": provider, "model": s.llm_model, "status": "error", "reachable": None,
                "model_available": None, "message": "Status check failed; see server logs."}
