"""MOCKED tests for the investigation workflow: no database, no network, no real LLM.

- MCP tools are called through the real MCP protocol (in-process client) against FakeTools.
- The LLM is a scripted FakeLLM; "llm" mode here never contacts a real provider.
- The API runs through FastAPI's TestClient with the store/manager dependencies overridden.
"""

import time
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.services import investigation_service
from app.services.investigation_service import InvestigationManager
from fakes import CHUNKS, P1, P2, FakeStore, FakeTools
from researchmind.agent import Investigator
from researchmind.investigation import build_structured
from researchmind.llm import get_llm
from researchmind.mcp_bridge import MCPToolClient, MCPToolError
from researchmind.tools import TOOL_SPECS

QUESTION = "Do graph attention models generalize to unseen proteins?"


def block(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


class FakeLLM:
    """Replays scripted Messages API responses and records each request (a MOCKED LLM)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def run_structured(inv: Investigator, question: str = QUESTION):
    result = inv.run(question)
    structured = build_structured(result, lookup=lambda ids: inv.tools.get_evidence(ids)["evidence"], corpus_size=3)
    return result, structured


# ---------------------------------------------------------------------- MCP tools, each independently

TOOL_CALLS = {
    "list_papers": ({}, lambda o: o["count"] == 3),
    "search_evidence": ({"query": "unseen proteins", "top_k": 3}, lambda o: len(o["results"]) == 3 and all(r["page"] for r in o["results"])),
    "get_paper": ({"paper_id": P1}, lambda o: o["title"] and o["findings"] and o["limitations"]),
    "explore_entity": ({"name": "GAT"}, lambda o: len(o["matches"][0]["papers"]) == 3),
    "find_related_papers": ({"paper_id": P1}, lambda o: all(r["paper_id"] != P1 for r in o["shared_entities"])),
    "compare_claims": ({"topic": "generalization"}, lambda o: len(o["statements_by_paper"]) >= 2 and o["contradictions"]),
    "find_research_gaps": ({"topic": "cold-start"}, lambda o: o["gaps"] and all(g["evidence"] for g in o["gaps"])),
    "get_evidence": ({"chunk_ids": [f"{P1}:c004"]}, lambda o: o["evidence"][0]["page"] == 2),
    "graph_query": ({"cypher": "MATCH (e:Method) RETURN e.name AS name"}, lambda o: o["rows"]),
}


def test_mcp_server_exposes_exactly_the_agent_tools():
    client = MCPToolClient(FakeTools())
    assert set(client.list_tools()) == {s["name"] for s in TOOL_SPECS} == set(TOOL_CALLS)


@pytest.mark.parametrize("name", sorted(TOOL_CALLS))
def test_each_mcp_tool_independently(name):
    tools = FakeTools()
    args, check = TOOL_CALLS[name]
    out = MCPToolClient(tools).call(name, args)
    assert check(out), out
    assert tools.calls[-1][0] == name  # the MCP call reached the tool implementation


def test_mcp_tool_schemas_match_agent_specs():
    """The agent advertises TOOL_SPECS to Claude; their required args must match the MCP server's."""
    import asyncio
    from mcp import Client
    server = MCPToolClient(FakeTools()).server

    async def schemas():
        async with Client(server) as c:
            return {t.name: t.input_schema for t in (await c.list_tools()).tools}
    mcp_schemas = asyncio.run(schemas())
    for spec in TOOL_SPECS:
        ours, theirs = spec["input_schema"], mcp_schemas[spec["name"]]
        assert set(ours["properties"]) == set(theirs.get("properties", {})), spec["name"]
        assert set(ours.get("required", [])) == set(theirs.get("required", [])), spec["name"]


def test_mcp_tool_failure_and_bad_arguments_are_reported():
    client = MCPToolClient(FakeTools(fail={"compare_claims"}))
    with pytest.raises(MCPToolError):
        client.call("compare_claims", {"topic": "x"})
    with pytest.raises(MCPToolError):
        client.call("get_paper", {"wrong_arg": 1})


def test_mcp_and_direct_transports_return_the_same_data():
    tools = FakeTools()
    via_mcp = MCPToolClient(tools).call("compare_claims", {"topic": "generalization"})
    assert via_mcp == tools.compare_claims("generalization")


# ---------------------------------------------------------------------- agent: offline plan (no LLM)

def test_offline_investigation_uses_mcp_tools_and_builds_cited_structure():
    tools = FakeTools()
    inv = Investigator(FakeStore(), use_llm=False, tools=tools)
    assert inv.transport == "mcp" and inv.mode == "offline"
    result, s = run_structured(inv)

    called = [c[0] for c in tools.calls]
    for t in ("list_papers", "search_evidence", "compare_claims", "explore_entity", "get_paper", "find_research_gaps"):
        assert t in called
    assert len({f["paper_id"] for f in s["findings"]}) == 3  # evidence from multiple papers
    assert any(c["kind"] == "contradiction" for c in s["comparisons"])
    assert s["method_comparison"][0]["entity"] == "Graph Attention Network" and len(s["method_comparison"][0]["papers"]) == 3
    assert s["limitations"] and s["gaps"]
    # Every source is real stored evidence; every citation number resolves to a source
    numbers = {src["n"] for src in s["sources"]}
    assert all(src["chunk_id"] in CHUNKS and src["page"] and src["paper_title"] for src in s["sources"])
    cited = ([n for f in s["findings"] for n in f["citations"]] + [n for g in s["gaps"] for n in g["citations"]] +
             [x[k]["citation"] for x in s["comparisons"] for k in ("a", "b")] + [n for l in s["limitations"] for n in l["citations"]])
    assert set(cited) <= numbers
    # Report citations use the same numbering as the sources list
    for ref in result.references:
        assert s["sources"][ref["n"] - 1]["chunk_id"] == ref["chunk_id"]
    # The phantom gap whose evidence is not in the graph was dropped; gaps are labelled as candidates
    assert "Phantom gap" not in [g["title"] for g in s["gaps"]]
    assert all(g["status"] == "candidate" and "not a confirmed" in g["note"] for g in s["gaps"])
    assert s["confidence"]["level"] in {"low", "moderate"}  # offline mode never claims high confidence
    assert any("Offline mode" in u for u in s["confidence"]["uncertainties"])
    assert s["summary"]


def test_direct_transport_gives_same_structure():
    a = run_structured(Investigator(FakeStore(), use_llm=False, tools=FakeTools(), transport="mcp"))[1]
    b = run_structured(Investigator(FakeStore(), use_llm=False, tools=FakeTools(), transport="direct"))[1]
    assert [f["text"] for f in a["findings"]] == [f["text"] for f in b["findings"]]
    assert [x["chunk_id"] for x in a["sources"]] == [x["chunk_id"] for x in b["sources"]]


def test_tool_failures_do_not_break_the_investigation():
    tools = FakeTools(fail={"compare_claims", "explore_entity", "graph_query"})
    inv = Investigator(FakeStore(), use_llm=False, tools=tools)
    result, s = run_structured(inv)
    failed = [st for st in result.steps if not st["ok"]]
    assert {st["tool"] for st in failed} >= {"compare_claims", "graph_query"}
    assert all(st["summary"].startswith("error:") for st in failed)
    # get_paper and gap finding still provide findings, limitations and gaps
    assert s["findings"] and s["limitations"] and s["gaps"]
    assert s["comparisons"] == []


def test_empty_corpus_returns_explanation():
    inv = Investigator(FakeStore(papers=False), use_llm=False, tools=FakeTools(store=FakeStore(papers=False)))
    result = inv.run(QUESTION)
    assert "No papers" in result.report_markdown and "Knowledge graph is empty." in result.warnings


# ---------------------------------------------------------------------- agent: mocked Claude loop

def scripted_claude(real_cid: str):
    return FakeLLM([
        SimpleNamespace(stop_reason="tool_use", content=[
            block("text", text="Search evidence, then traverse from the GAT method."),
            block("tool_use", id="tu_1", name="search_evidence", input={"query": "unseen proteins", "top_k": 4}),
            block("tool_use", id="tu_2", name="explore_entity", input={"name": "Graph Attention Network"}),
        ]),
        SimpleNamespace(stop_reason="end_turn", content=[block("text", text=(
            "# Report\n\n## Answer\nEvidence is mixed: one paper reports generalization [" + real_cid + "], "
            "another reports failure [" + f"{P2}:c002" + "]. Invented [p_000000000000:c999].\n\n"
            "## Confidence\nModerate: two papers conflict.\n"))]),
    ])


def test_claude_mode_with_mocked_llm():
    tools = FakeTools()
    llm = scripted_claude(f"{P1}:c004")
    inv = Investigator(FakeStore(), llm=llm, tools=tools)
    result, s = run_structured(inv)

    assert result.mode == "llm"
    agent_steps = [st["tool"] for st in result.steps if st["source"] == "agent"]
    coverage_steps = [st["tool"] for st in result.steps if st["source"] == "coverage"]
    assert agent_steps == ["search_evidence", "explore_entity"]
    assert {"compare_claims", "find_research_gaps", "get_paper"} <= set(coverage_steps)
    # Tool results were returned to the model via the MCP bridge
    tool_msg = llm.requests[1]["messages"][2]
    assert [c["tool_use_id"] for c in tool_msg["content"]] == ["tu_1", "tu_2"]
    # Fabricated citation is flagged, real ones are numbered and verified
    assert "[unverified]" in result.report_markdown and "[1]" in result.report_markdown
    assert any("p_000000000000:c999" in w for w in result.warnings)
    assert s["sources"][0]["chunk_id"] == f"{P1}:c004" and s["sources"][0]["cited_in_report"]
    assert s["summary"].startswith("Evidence is mixed") and "[1]" in s["summary"]
    assert s["confidence"]["narrative"].startswith("Moderate")
    assert any("did not match stored evidence" in u for u in s["confidence"]["uncertainties"])


def test_missing_credentials_means_offline(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert get_llm() is None
    assert Investigator(FakeStore(), tools=FakeTools()).mode == "offline"


def test_rejected_credentials_fall_back_to_offline():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    err = anthropic.AuthenticationError("invalid x-api-key", response=httpx.Response(401, request=req), body=None)
    inv = Investigator(FakeStore(), llm=FakeLLM([err]), tools=FakeTools())
    result, s = run_structured(inv)
    assert result.mode == "offline" and s["findings"]
    assert any("credentials rejected" in w for w in result.warnings)


def test_llm_outage_falls_back_to_offline():
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    inv = Investigator(FakeStore(), llm=FakeLLM([anthropic.APIConnectionError(request=req)]), tools=FakeTools())
    result = inv.run(QUESTION)
    assert result.mode == "offline" and any("Claude API error" in w for w in result.warnings)


def test_time_budget_forces_report():
    llm = FakeLLM([SimpleNamespace(stop_reason="end_turn", content=[block("text", text="## Answer\nPartial answer.")])])
    inv = Investigator(FakeStore(), llm=llm, tools=FakeTools(), time_budget_s=1e-9)
    time.sleep(0.001)
    result = inv.run(QUESTION)
    assert llm.requests[0]["tool_choice"] == {"type": "none"}  # no further tool calls allowed
    assert any("time budget" in w for w in result.warnings)


# ---------------------------------------------------------------------- FastAPI endpoint

def make_factory(tools_factory=FakeTools, llm=None):
    def factory(store, use_llm=True, time_budget_s=None):
        return Investigator(store, llm=llm, use_llm=use_llm and llm is not None, tools=tools_factory(), time_budget_s=time_budget_s)
    return factory


@pytest.fixture
def api(monkeypatch):
    """TestClient with a fake store and a fresh manager; returns (client, set_manager)."""
    database.reset_store()
    state = {"store": FakeStore(), "manager": InvestigationManager(2, 30, investigator_factory=make_factory())}
    app.dependency_overrides[database.get_store] = lambda: state["store"]
    app.dependency_overrides[investigation_service.get_manager] = lambda: state["manager"]
    yield TestClient(app), state
    app.dependency_overrides.clear()
    database.reset_store()


def test_api_investigation_wait(api):
    client, _ = api
    r = client.post("/api/investigations", json={"question": QUESTION})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed" and body["mode"] == "offline" and body["id"].startswith("inv_")
    res = body["result"]
    for key in ("summary", "findings", "comparisons", "gaps", "limitations", "confidence", "sources", "papers", "report_markdown"):
        assert res[key], key
    assert {s["paper_id"] for s in res["sources"]} <= {P1, P2, "p_ccccccccccc3"}
    assert all(s["chunk_id"] in CHUNKS and s["page"] for s in res["sources"])
    assert any(e["type"] == "tool_call" for e in body["progress"]) and body["progress"][-1]["type"] == "done"
    assert body["duration_seconds"] is not None


def test_api_investigation_async_poll(api):
    client, _ = api
    r = client.post("/api/investigations", json={"question": QUESTION, "wait": False})
    assert r.status_code == 202 and r.json()["status"] in {"queued", "running"}
    inv_id = r.json()["id"]
    for _ in range(100):
        body = client.get(f"/api/investigations/{inv_id}").json()
        if body["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert body["status"] == "completed" and body["result"]["gaps"]
    listed = client.get("/api/investigations").json()["investigations"]
    assert listed[0]["id"] == inv_id


@pytest.mark.parametrize("payload, where", [
    ({}, "question"), ({"question": "short"}, "question"), ({"question": "x" * 1001}, "question"),
    ({"question": QUESTION, "wait": "maybe"}, "wait"),
])
def test_api_validates_input(api, payload, where):
    client, _ = api
    r = client.post("/api/investigations", json=payload)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert where in r.json()["error"]["message"]


def test_api_rejects_empty_corpus(api):
    client, state = api
    state["store"] = FakeStore(papers=False)
    r = client.post("/api/investigations", json={"question": QUESTION})
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_papers"


def test_api_without_database(monkeypatch):
    database.reset_store()
    monkeypatch.setenv("FALKORDB_URL", "falkor://default:SuperSecret123@localhost:1")
    r = TestClient(app).post("/api/investigations", json={"question": QUESTION})
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
    assert "SuperSecret123" not in r.text
    database.reset_store()


def test_api_internal_failure_hides_details(api):
    client, state = api

    def broken(store, **kw):
        raise RuntimeError("secret internal detail sk-ant-123")
    state["manager"] = InvestigationManager(1, 30, investigator_factory=broken)
    r = client.post("/api/investigations", json={"question": QUESTION})
    assert r.status_code == 500 and r.json()["error"]["code"] == "investigation_failed"
    assert "secret" not in r.text and "sk-ant" not in r.text and "Traceback" not in r.text


def test_api_database_drop_during_investigation(api):
    from redis.exceptions import ConnectionError as RedisConnectionError
    client, state = api

    class DroppingTools(FakeTools):
        def get_evidence(self, chunk_ids):
            raise RedisConnectionError("connection reset")
    state["manager"] = InvestigationManager(1, 30, investigator_factory=make_factory(DroppingTools))
    r = client.post("/api/investigations", json={"question": QUESTION})
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"


def test_api_limits_concurrency(api):
    client, state = api

    class SlowTools(FakeTools):
        def list_papers(self):
            time.sleep(0.5)
            return super().list_papers()
    state["manager"] = InvestigationManager(1, 30, investigator_factory=make_factory(SlowTools))
    first = client.post("/api/investigations", json={"question": QUESTION, "wait": False})
    second = client.post("/api/investigations", json={"question": QUESTION, "wait": False})
    assert first.status_code == 202
    assert second.status_code == 429 and second.json()["error"]["code"] == "busy"


def test_api_unknown_and_malformed_ids(api):
    client, _ = api
    assert client.get("/api/investigations/inv_000000000000").status_code == 404
    assert client.get("/api/investigations/not-an-id").status_code == 422


def test_api_with_mocked_llm(api):
    client, state = api
    state["manager"] = InvestigationManager(1, 30, investigator_factory=make_factory(llm=scripted_claude(f"{P1}:c004")))
    body = client.post("/api/investigations", json={"question": QUESTION}).json()
    assert body["status"] == "completed" and body["mode"] == "llm"
    assert body["result"]["summary"].startswith("Evidence is mixed")
    assert any("unverified" in w or "does not match" in w for w in body["result"]["warnings"])


# ---------------------------------------------------------------------- relevance: off-topic questions

class OffTopicTools(FakeTools):
    """Same corpus, but nothing scores above the relevance threshold (like asking about cake recipes)."""

    def search_evidence(self, query, top_k=6, paper_id=None):
        out = super().search_evidence(query, top_k, paper_id)
        for r in out["results"]:
            r["score"] = 0.2
        return out

    def compare_claims(self, topic, top_k=10):
        out = super().compare_claims(topic, top_k)
        for stmts in out["statements_by_paper"].values():
            for s in stmts:
                s["relevance"] = 0.15
        return out

    def find_research_gaps(self, topic=None, max_gaps=8):
        self._enter("find_research_gaps", topic=topic, max_gaps=max_gaps)
        return {"topic": topic, "note": "", "gaps": []}


@pytest.mark.parametrize("llm", [None, "claude"])
def test_off_topic_question_reports_no_evidence(llm):
    fake_llm = FakeLLM([SimpleNamespace(stop_reason="end_turn", content=[block("text", text=(
        "## Answer\nThe papers do not address this.\n"))])]) if llm else None
    inv = Investigator(FakeStore(), llm=fake_llm, use_llm=bool(llm), tools=OffTopicTools())
    result, s = run_structured(inv, "What is the best recipe for chocolate cake?")
    assert s["evidence_found"] is False
    assert s["findings"] == [] and s["comparisons"] == [] and s["gaps"] == [] and s["limitations"] == []
    assert s["confidence"]["level"] == "low"
    assert "do not contain evidence relevant" in s["summary"]
    if not llm:
        assert "do not contain evidence relevant" in result.report_markdown
        assert "get_paper" not in [st["tool"] for st in result.steps]  # irrelevant papers are not pulled in


def test_low_relevance_statements_are_filtered():
    class Mixed(FakeTools):
        def compare_claims(self, topic, top_k=10):
            out = super().compare_claims(topic, top_k)
            for stmts in out["statements_by_paper"].values():
                for s in stmts:
                    if s["paper_id"] == "p_ccccccccccc3":
                        s["relevance"] = 0.1
            return out
    _, s = run_structured(Investigator(FakeStore(), use_llm=False, tools=Mixed()))
    assert s["evidence_found"]
    stmt_texts = [f["text"] for f in s["findings"] if f["relevance"] is not None]
    assert stmt_texts and not any("Structure-aware GNNs outperform" in t for t in stmt_texts)
