"""INTEGRATION tests: the investigation workflow against a real FalkorDB with the sample PDFs.

Real graph, real MCP tools, real HTTP stack, a real account. The LLM is NOT used (offline plan, as
AI_REQUIRED=false in tests), so these run without a model. Writes only to the throwaway graph `researchmind_pytest_inv`.
Skipped automatically when no FalkorDB is reachable.
"""

import os

import pytest

from app import database
from app.main import app
from authclient import Client, sign_up
from researchmind.config import get_settings
from researchmind.graph import GraphConnectionError, GraphStore
from researchmind.mcp_bridge import MCPToolClient
from researchmind.tools import ResearchTools

pytestmark = pytest.mark.integration
INV_GRAPH = "researchmind_pytest_inv"
QUESTION = "Do graph attention models generalize to unseen proteins in cold-start drug-target prediction?"


@pytest.fixture(scope="module")
def env(sample_pdfs):
    url = os.getenv("FALKORDB_TEST_URL") or get_settings().falkordb_url
    if not url:
        pytest.skip("No FALKORDB_TEST_URL / FALKORDB_URL configured")
    try:
        store = GraphStore(url=url, graph_name=INV_GRAPH)
    except GraphConnectionError as e:
        pytest.skip(f"FalkorDB not reachable: {e}")
    store.reset()
    mp = pytest.MonkeyPatch()
    mp.setenv("FALKORDB_URL", url)
    mp.setenv("FALKORDB_GRAPH", INV_GRAPH)
    database.reset_store()
    with Client(app) as client:
        client.get("/api/auth/csrf")
        _, _, pid = sign_up(client)
        client.project = f"/api/projects/{pid}"
        files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in sample_pdfs]
        r = client.post(f"{client.project}/papers/upload", files=files)
        assert r.json()["summary"]["processed"] == 3, r.text
        owner = client.get("/api/auth/me").json()["id"]
        yield client, database.store_for(database.get_registry().get_project(pid, owner))
    database.reset_store()
    mp.undo()
    store.graph.delete()
    for g in store.db.list_graphs():  # the project registry created by the API
        if g.startswith(INV_GRAPH):
            store.db.select_graph(g).delete()
    store.close()


def test_mcp_tools_on_real_graph(env):
    _, store = env
    mcp = MCPToolClient(ResearchTools(store))
    papers = mcp.call("list_papers", {})["papers"]
    assert len(papers) == 3
    hits = mcp.call("search_evidence", {"query": "unseen proteins cold-start", "top_k": 4})["results"]
    assert hits and all(h["page"] >= 1 and h["paper_id"] in {p["id"] for p in papers} for h in hits)
    assert all(len(m["papers"]) == 1 for m in mcp.call("explore_entity", {"name": "Graph Attention Network"})["matches"])
    assert mcp.call("compare_claims", {"topic": "generalization to unseen proteins"})["contradictions"] == []
    paper = mcp.call("get_paper", {"paper_id": papers[0]["id"]})
    assert {"methods", "datasets", "claims", "findings", "limitations"} <= set(paper)
    assert mcp.call("find_research_gaps", {"topic": "cold-start"})["gaps"]
    assert "error" in mcp.call("graph_query", {"cypher": "MATCH (n) DETACH DELETE n"})


def test_investigation_endpoint_cites_real_evidence(env):
    client, store = env
    paper_id = next(p["id"] for p in client.get(f"{client.project}/papers").json()["papers"]
                    if "Graph Attention" in (p["title"] or ""))
    r = client.post(f"{client.project}/investigations", json={"question": QUESTION, "paper_id": paper_id, "wait": True})
    assert r.status_code == 200, r.text
    body = r.json()
    res = body["result"]
    assert body["status"] == "completed" and body["mode"] == "offline"
    assert res["findings"] and res["sources"] and res["limitations"]
    assert {f["paper_id"] for f in res["findings"]} == {paper_id} and res["comparisons"] == []

    # Every source must be a stored chunk of a stored paper, on the page the API reports.
    rows = store.query("""UNWIND $ids AS cid MATCH (p:Paper)-[:HAS_CHUNK]->(c:Chunk {id: cid})
                          RETURN c.id AS id, p.id AS paper_id, c.page AS page""",
                       {"ids": [s["chunk_id"] for s in res["sources"]]})
    stored = {r["id"]: r for r in rows}
    for s in res["sources"]:
        assert s["chunk_id"] in stored, s
        assert stored[s["chunk_id"]]["paper_id"] == s["paper_id"]
        assert stored[s["chunk_id"]]["page"] == s["page"]
    numbers = {s["n"] for s in res["sources"]}
    assert {n for g in res["gaps"] for n in g["citations"]} <= numbers
    assert "[unverified]" not in res["report_markdown"]
