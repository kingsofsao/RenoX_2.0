"""Thin wrapper around the Anthropic SDK used by the extractor and the agent."""

from __future__ import annotations

import logging

import anthropic

from .config import get_settings

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMUnavailable(Exception):
    pass


class ClaudeLLM:
    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.anthropic_model
        self.client = anthropic.Anthropic(max_retries=3)
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


def get_llm() -> ClaudeLLM | None:
    """Return a Claude client if credentials are configured, otherwise None (offline mode)."""
    if not get_settings().has_llm:
        return None
    return ClaudeLLM()
