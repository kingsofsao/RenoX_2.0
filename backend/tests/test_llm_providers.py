"""MOCKED tests for LLM providers and the grounded (Ollama) investigation path.

- OllamaLLM talks to an httpx.MockTransport that imitates Ollama's REST API; no Ollama process is used.
- The grounded agent uses ScriptedChat, a fake model returning canned answers; no real inference happens.
Real Ollama inference is covered by test_ollama_live.py (skipped unless Ollama and the model are available).
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.services import investigation_service
from app.services.investigation_service import InvestigationManager
from fakes import CHUNKS, P1, P2, FakeStore, FakeTools
from researchmind import llm as llm_mod
from researchmind.agent import Investigator
from researchmind.investigation import build_structured
from researchmind.llm import ChatResult, LLMUnavailable, OllamaLLM, get_llm, llm_status

QUESTION = "Do graph attention models generalize to unseen proteins?"


# ---------------------------------------------------------------------- Ollama client against a mock API

def ollama_api(models=("qwen2.5:1.5b",), chat_lines=None, chat_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.4"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": m} for m in models]})
        if request.url.path == "/api/chat":
            if chat_status != 200:
                return httpx.Response(chat_status, json={"error": f"model 'x' not found"})
            return httpx.Response(200, content="\n".join(json.dumps(x) for x in (chat_lines or [])).encode())
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def refused(request):
    raise httpx.ConnectError("connection refused", request=request)


def test_status_ready_and_model_missing():
    ok = OllamaLLM(model="qwen2.5:1.5b", transport=ollama_api()).status()
    assert ok["status"] == "ready" and ok["reachable"] and ok["model_available"]
    missing = OllamaLLM(model="llama3.2:3b", transport=ollama_api()).status()
    assert missing["status"] == "model_missing" and "ollama pull llama3.2:3b" in missing["message"]
    bare = OllamaLLM(model="qwen2.5", transport=ollama_api(models=("qwen2.5:latest",))).status()
    assert bare["status"] == "ready"  # "qwen2.5" means the :latest tag


def test_status_unreachable_and_not_configured(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)  # backend/.env may configure one
    down = OllamaLLM(model="qwen2.5:1.5b", transport=httpx.MockTransport(refused)).status()
    assert down["status"] == "unreachable" and not down["reachable"] and "Start the Ollama app" in down["message"]
    assert OllamaLLM(model=None, transport=ollama_api()).status()["status"] == "not_configured"


def test_chat_streams_text_and_tool_calls():
    lines = [{"message": {"content": "Hello "}}, {"message": {"content": "world [S1]"}},
             {"message": {"content": "", "tool_calls": [{"function": {"name": "search_evidence", "arguments": {"query": "x"}}}]}},
             {"done": True, "done_reason": "stop", "eval_count": 12}]
    progress = []
    r = OllamaLLM(model="m", transport=ollama_api(chat_lines=lines)).chat([{"role": "user", "content": "hi"}], on_progress=progress.append)
    assert r.text == "Hello world [S1]" and r.eval_tokens == 12
    assert r.tool_calls == [{"name": "search_evidence", "arguments": {"query": "x"}}] and r.done_reason == "tool_calls"


def test_chat_strips_thinking_and_reports_length():
    lines = [{"message": {"content": "<think>secret plan</think>Answer"}}, {"done": True, "done_reason": "length"}]
    r = OllamaLLM(model="m", transport=ollama_api(chat_lines=lines)).chat([])
    assert r.text == "Answer" and r.done_reason == "length"


@pytest.mark.parametrize("transport, code", [
    (ollama_api(chat_status=404), "model_missing"),
    (ollama_api(chat_status=500), "http_error"),
    (httpx.MockTransport(refused), "unreachable"),
])
def test_chat_errors_are_classified(transport, code):
    with pytest.raises(LLMUnavailable) as e:
        OllamaLLM(model="m", transport=transport).chat([])
    assert e.value.code == code


def test_chat_malformed_stream():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b'{"message": {"content": "ok"}}\nnot json'))
    with pytest.raises(LLMUnavailable) as e:
        OllamaLLM(model="m", transport=transport).chat([])
    assert e.value.code == "malformed"


def test_chat_timeout():
    def slow(request):
        raise httpx.ReadTimeout("timed out", request=request)
    with pytest.raises(LLMUnavailable) as e:
        OllamaLLM(model="m", transport=httpx.MockTransport(slow), timeout_s=1).chat([])
    assert e.value.code == "timeout"


def test_provider_selection(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "none")
    assert get_llm() is None and llm_status()["status"] == "not_configured"
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")  # no key -> offline, with a clear hint
    assert get_llm() is None and "ANTHROPIC_API_KEY" in llm_status()["message"]
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:1.5b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")  # nothing listens here
    llm = get_llm()
    assert isinstance(llm, OllamaLLM) and llm.model == "qwen2.5:1.5b"
    st = llm_status()
    assert st["provider"] == "ollama" and st["status"] == "unreachable"


def test_extraction_never_uses_ollama(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:1.5b")
    assert llm_mod.get_extraction_llm() is None  # uploads keep the heuristic extractor


# ---------------------------------------------------------------------- grounded agent with a scripted model

class ScriptedChat:
    """Fake chat() model: returns scripted ChatResults (or raises) and records every request."""
    provider, model = "ollama", "fake:1b"

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def chat(self, messages, tools=None, on_progress=None):
        self.requests.append({"messages": [dict(m) for m in messages], "tools": tools})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def sid_of(llm, chunk_id):
    """The [S#] label the prompt gave to a chunk (parsed from the first request)."""
    prompt = llm.requests[0]["messages"][1]["content"]
    for line in prompt.splitlines():
        if line.startswith("[S") and CHUNKS[chunk_id][3][:40] in line:
            return line.split("]")[0][1:]
    raise AssertionError(f"{chunk_id} not in prompt")


def report(*cites, extra=""):
    return ChatResult(text=(
        "## Answer\nThe papers disagree on generalization " + " ".join(f"[{c}]" for c in cites) + ".\n"
        "## Evidence from the papers\n- One reports gains [S1].\n## Comparison\nThey differ [S2].\n"
        "## Conflicts and uncertainty\nConflicting results [S1, S2].\n## Candidate research gaps\nHypothesis: cold-start study [S2].\n"
        "## Not covered by the evidence\nNothing else.\n## Confidence\nModerate." + extra))


def run(llm, tools=None, requirements=None, question=QUESTION):
    inv = Investigator(FakeStore(), llm=llm, tools=tools or FakeTools())
    result = inv.run(question, requirements=requirements)
    return inv, result, build_structured(result, lambda ids: inv.tools.get_evidence(ids)["evidence"], corpus_size=3)


def test_grounded_report_maps_sources_to_verified_evidence():
    llm = ScriptedChat([report("S1", "S2")])
    inv, result, s = run(llm)
    assert result.mode == "llm" and result.provider == "ollama" and result.model == "fake:1b"
    prompt = llm.requests[0]["messages"][1]["content"]
    assert "RESEARCH QUESTION" in prompt and "[S1]" in prompt and "page" in prompt
    assert llm.requests[0]["tools"][0]["function"]["name"] == "search_evidence"  # iterative search offered
    assert "SOURCES" in prompt and "CONFLICTS DETECTED" in prompt
    # [S#] became numbered references to real stored chunks
    assert result.references and all(r["chunk_id"] in CHUNKS for r in result.references)
    assert "[S1]" not in result.report_markdown and "[1]" in result.report_markdown
    assert "LLM report generated by **ollama / fake:1b**" in result.report_markdown
    assert s["summary"].startswith("The papers disagree") and s["evidence_found"]
    # No warning about the model's citations (the fake corpus's phantom gap is reported separately)
    assert not [w for w in result.warnings if "model" in w or "unverified" in w or "quotation" in w]


def test_grounded_model_can_request_more_evidence():
    llm = ScriptedChat([ChatResult(text="", tool_calls=[{"name": "search_evidence", "arguments": {"query": "cold start AUC"}}]),
                        report("S1")])
    _, result, _ = run(llm)
    assert [st["tool"] for st in result.steps if st["source"] == "llm"] == ["search_evidence"]
    tool_msg = llm.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and ("NEW SOURCES" in tool_msg["content"] or "No additional" in tool_msg["content"])


def test_grounded_tool_rounds_are_limited(monkeypatch):
    monkeypatch.setenv("LLM_MAX_TOOL_ROUNDS", "1")
    ask = ChatResult(text="", tool_calls=[{"name": "search_evidence", "arguments": {"query": "more"}}])
    llm = ScriptedChat([ask, report("S1")])
    run(llm)
    assert llm.requests[0]["tools"] and llm.requests[1]["tools"] is None  # second call: no tools offered


def test_grounded_flags_invented_sources_and_quotes():
    llm = ScriptedChat([report("S1", "S99", extra='\nThe paper says "TAGSY measures heart rate with a PPG sensor continuously".')])
    _, result, _ = run(llm)
    assert "[unverified]" in result.report_markdown
    assert "[quote not found in sources]" in result.report_markdown
    assert any("S99" in w for w in result.warnings) and any("quotation" in w for w in result.warnings)


def test_grounded_requirements_are_labelled_not_evidence():
    reqs = "KidBrace must monitor infant heart rate and temperature and alert parents."
    llm = ScriptedChat([report("S1", "R")])
    _, result, _ = run(llm, requirements=reqs)
    prompt = llm.requests[0]["messages"][1]["content"]
    assert "USER-PROVIDED PROJECT REQUIREMENTS [R] (not from the papers)" in prompt and reqs in prompt
    assert "[R]" in result.report_markdown and "your own requirements" in result.report_markdown
    assert result.requirements == reqs


@pytest.mark.parametrize("bad", [
    ChatResult(text="I think graph models are great."),     # no citations at all
    ChatResult(text=""),                                     # empty
])
def test_grounded_malformed_answers_fall_back_to_offline(bad):
    _, result, s = run(ScriptedChat([bad]))
    assert result.mode == "offline" and result.references
    assert any("malformed" in w for w in result.warnings)


@pytest.mark.parametrize("code", ["unreachable", "model_missing", "timeout"])
def test_grounded_provider_failures_fall_back_to_offline(code):
    _, result, s = run(ScriptedChat([LLMUnavailable("down", code)]))
    assert result.mode == "offline" and s["findings"]
    assert any(code in w for w in result.warnings)


def test_grounded_no_relevant_evidence_skips_the_model():
    from test_investigation_mocked import OffTopicTools
    llm = ScriptedChat([])
    _, result, s = run(llm, tools=OffTopicTools(), question="Best chocolate cake recipe?")
    assert llm.requests == [] and result.mode == "offline" and not s["evidence_found"]
    assert any("LLM was not asked" in w for w in result.warnings)


# ---------------------------------------------------------------------- API

@pytest.fixture
def client():
    database.reset_store()
    yield TestClient(app)
    app.dependency_overrides.clear()
    database.reset_store()


def test_llm_status_endpoint_and_health(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:1.5b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:9")
    st = client.get("/api/llm/status").json()
    assert st["provider"] == "ollama" and st["status"] == "unreachable" and st["model"] == "qwen2.5:1.5b"
    health = client.get("/api/health").json()
    assert health["config"]["llm"]["status"] == "unreachable" and health["config"]["llm_configured"] is True
    assert "ANTHROPIC" not in json.dumps(health)


def test_api_reports_provider_and_requirements(client):
    store = FakeStore()
    manager = InvestigationManager(1, 30, investigator_factory=lambda s, use_llm=True, time_budget_s=None:
                                   Investigator(s, llm=ScriptedChat([report("S1", "R")]), tools=FakeTools()))
    app.dependency_overrides[database.get_store] = lambda: store
    app.dependency_overrides[investigation_service.get_manager] = lambda: manager
    body = client.post("/api/investigations", json={"question": QUESTION, "requirements": "Must track infant temperature."}).json()
    assert body["status"] == "completed" and body["mode"] == "llm"
    assert body["provider"] == "ollama" and body["model"] == "fake:1b" and body["requirements"] == "Must track infant temperature."
    assert any("Using LLM ollama / fake:1b" in e["message"] for e in body["progress"])
    r = client.post("/api/investigations", json={"question": QUESTION, "requirements": "x" * 3001})
    assert r.status_code == 422 and "requirements" in r.json()["error"]["message"]


# ---------------------------------------------------------------------- attribution guard (regression from a real run)

def test_attribution_guard_flags_features_borrowed_from_another_paper():
    """Sentences below were produced by qwen2.5:1.5b in a real TAGSY vs CK KidBrace investigation.
    TAGSY (p_0bda...) is a Wi-Fi location tracker; the ESP32/MAX30102 hardware belongs to the KidBrace pitch deck."""
    from researchmind.grounded import _attribution_problems, _system_names
    deck, tagsy = "Copy of SAIRAM SDG SOLVEATHON 4.0", "CHILD MONITORING SYSTEM - TAGSY"
    sources = {
        "S1": {"paper_title": deck, "text": "HARDWARE: ESP32 microcontroller, MAX30102 (heart rate & SpO2), DS18B20, NEO-6M GPS, SIM800L GSM."},
        "S5": {"paper_title": deck, "text": "CK–KidBrace is a smart, wearable sensor-based system designed for children aged 4–15 years."},
        "S11": {"paper_title": tagsy, "text": "WFPS, a WIFI positioning system, will be used to track the child's whereabouts."},
    }
    names = _system_names("How does the TAGSY child monitoring system compare with the CK KidBrace infant wearable?")
    assert names == {"TAGSY", "KidBrace"}
    report_text = "\n".join([
        "## Answer",
        "The TAGSY system uses an ESP32 microcontroller, MAX30102, NEO-6M GPS and SIM800L GSM [S1].",   # borrowed: flag
        "The TAGSY system uses a WIFI positioning system to track the child's whereabouts [S11].",      # correct
        "The CK KidBrace is designed for children aged 4–15 years [S5].",                              # correct
        "The CK KidBrace uses the same ESP32 hardware [S1].",                                          # same paper as S5: ok
        "## Comparison",
        "- The TAGSY system integrates a mobile application that displays health data, while the CK KidBrace uses a WIFI positioning system.",  # uncited
        "- Both systems aim to provide real-time location tracking and health monitoring.",            # generalisation, uncited
        "- Both systems track location [S11, S5].",                                                    # each system has a source: ok
        "## Candidate research gaps",
        "Hypothesis: TAGSY lacks health monitoring [S11].",                                            # not checked
    ])
    problems = _attribution_problems(report_text, sources, names)
    flagged = {s[:40]: p for s, p in problems}
    assert flagged == {
        "The TAGSY system uses an ESP32 microcont": "cited sources do not mention TAGSY",
        "- The TAGSY system integrates a mobile a": "no citation",
        "- Both systems aim to provide real-time ": "no citation",
    }


def test_attribution_markers_appear_in_report():
    llm = ScriptedChat([ChatResult(text=(
        "## Answer\nThe papers disagree [S1, S2].\n## Evidence from the papers\n"
        "- DTIGAT generalizes well [S1].\n- DTIGAT needs no structure.\n## Confidence\nLow."))])
    _, result, _ = run(llm, question="Does DTIGAT generalize to unseen proteins?")
    assert "[uncited claim]" in result.report_markdown
    assert any("named systems" in w for w in result.warnings)
