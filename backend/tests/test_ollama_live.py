"""LIVE tests: REAL inference with the configured Ollama model (LLM_PROVIDER=ollama, LLM_MODEL).

Skipped unless Ollama is reachable and the model is installed. Slow on CPU-only machines
(minutes per test). Uses the in-memory fake corpus, so no database is needed.

    python -m pytest -q -m live_llm
"""

import pytest

from fakes import CHUNKS, FakeStore, FakeTools
from researchmind.agent import Investigator
from researchmind.investigation import build_structured
from researchmind.llm import OllamaLLM

pytestmark = pytest.mark.live_llm


@pytest.fixture(scope="module")
def ollama():
    llm = OllamaLLM()
    st = llm.status()
    if st["status"] != "ready":
        pytest.skip(f"Ollama not ready: {st['status']} - {st['message']}")
    return llm


def test_live_status(ollama):
    st = ollama.status()
    assert st["reachable"] and st["model_available"] and st["model"] == ollama.model


def test_live_chat(ollama):
    r = ollama.chat([{"role": "user", "content": "Reply with exactly the word READY and nothing else."}])
    assert "READY" in r.text.upper() and r.eval_tokens > 0


def test_live_grounded_investigation(ollama):
    inv = Investigator(FakeStore(), llm=ollama, tools=FakeTools(), time_budget_s=900)
    result = inv.run("Do graph attention models generalize to unseen proteins?")
    s = build_structured(result, lambda ids: inv.tools.get_evidence(ids)["evidence"], corpus_size=3)
    assert result.mode == "llm", result.warnings
    assert result.references, "the model must cite at least one source"
    assert all(r["chunk_id"] in CHUNKS for r in result.references)  # every citation is stored evidence
    assert "## Answer" in result.report_markdown and s["summary"]
