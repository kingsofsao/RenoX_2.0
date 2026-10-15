"""INTEGRATION: project isolation, saved investigations and evidence quality on a real FalkorDB.

Two projects with deliberately unrelated papers:
  A = three synthetic drug-target papers      B = two synthetic urban-beekeeping papers
Questions in one project must never retrieve the other's evidence - via the API, the MCP tools,
vector search or free-form Cypher. Writes only to throwaway graphs `researchmind_pytest_proj*`,
which are deleted afterwards. No LLM is used (offline plan); see test_ollama_live.py for real models.
"""

import os

import pytest
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.services import investigation_service
from researchmind.config import get_settings
from researchmind.mcp_bridge import MCPToolClient
from researchmind.tools import ResearchTools
from unrelated_pdfs import make_bee_pdfs

pytestmark = pytest.mark.integration
BASE = "researchmind_pytest_proj"
DTI_Q = "Do graph attention models generalize to unseen proteins in drug-target prediction?"
BEE_Q = "How does shelter affect honeybee colony winter survival on rooftops?"


def drop_graphs(url: str) -> None:
    from falkordb import FalkorDB
    db = FalkorDB.from_url(url)
    for g in db.list_graphs():
        if g.startswith(BASE):
            db.select_graph(g).delete()
    db.close()


@pytest.fixture(scope="module")
def env(sample_pdfs, tmp_path_factory):
    url = os.getenv("FALKORDB_TEST_URL") or get_settings().falkordb_url
    if not url:
        pytest.skip("No FALKORDB_TEST_URL / FALKORDB_URL configured")
    try:
        drop_graphs(url)
    except Exception as e:
        pytest.skip(f"FalkorDB not reachable: {e}")
    mp = pytest.MonkeyPatch()
    mp.setenv("FALKORDB_URL", url)
    mp.setenv("FALKORDB_GRAPH", BASE)
    database.reset_store()
    investigation_service._manager = None
    bees = make_bee_pdfs(tmp_path_factory.mktemp("bees"))
    with TestClient(app) as client:
        a = client.post("/api/projects", json={"name": "Drug targets"}).json()
        b = client.post("/api/projects", json={"name": "Urban bees"}).json()
        for pid, pdfs in ((a["id"], sample_pdfs), (b["id"], bees)):
            files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in pdfs]
            r = client.post(f"/api/projects/{pid}/papers/upload", files=files)
            assert r.json()["summary"]["processed"] == len(pdfs), r.text
        yield client, a["id"], b["id"], url
    database.reset_store()
    investigation_service._manager = None
    mp.undo()
    drop_graphs(url)


def paper_ids(client, pid):
    return {p["id"] for p in client.get(f"/api/projects/{pid}/papers").json()["papers"]}


def investigate(client, pid, question):
    r = client.post(f"/api/projects/{pid}/investigations", json={"question": question, "use_llm": False})
    assert r.status_code == 200, r.text
    return r.json()


def test_each_project_lists_only_its_papers(env):
    client, a, b, _ = env
    pa, pb = paper_ids(client, a), paper_ids(client, b)
    assert len(pa) == 3 and len(pb) == 2 and not pa & pb
    assert client.get("/api/papers").json()["counts"]["total"] == 0  # legacy route = Default project, untouched
    projects = {p["id"]: p for p in client.get("/api/projects").json()["projects"]}
    assert projects[a]["paper_count"] == 3 and projects[b]["paper_count"] == 2 and projects["default"]["is_default"]


def test_tools_cannot_reach_another_projects_graph(env):
    client, a, b, _ = env
    pa, pb = paper_ids(client, a), paper_ids(client, b)
    reg = database.get_registry()
    for pid, own, other_question in ((a, pa, BEE_Q), (b, pb, DTI_Q)):
        tools = ResearchTools(database.store_for(reg.get_project(pid)))
        mcp = MCPToolClient(tools)
        hits = mcp.call("search_evidence", {"query": other_question, "top_k": 15})["results"]
        assert {h["paper_id"] for h in hits} <= own  # vector + keyword search see only this project
        rows = mcp.call("graph_query", {"cypher": "MATCH (p:Paper) RETURN p.id AS id"})["rows"]
        assert {r["id"] for r in rows} == own  # even free-form Cypher is confined to the project graph
        claims = mcp.call("compare_claims", {"topic": other_question})["statements_by_paper"]
        assert {s["paper_id"] for v in claims.values() for s in v} <= own


def test_questions_never_retrieve_the_other_projects_evidence(env):
    client, a, b, _ = env
    pa, pb = paper_ids(client, a), paper_ids(client, b)
    bee_in_a = investigate(client, a, BEE_Q)["result"]
    assert bee_in_a["evidence_found"] is False and bee_in_a["sources"] == [] and bee_in_a["confidence"]["level"] == "low"
    dti_in_b = investigate(client, b, DTI_Q)["result"]
    assert dti_in_b["evidence_found"] is False and dti_in_b["sources"] == []

    bee_in_b = investigate(client, b, BEE_Q)["result"]
    assert bee_in_b["evidence_found"] and bee_in_b["sources"]
    assert {s["paper_id"] for s in bee_in_b["sources"]} <= pb
    dti_in_a = investigate(client, a, DTI_Q)["result"]
    assert {s["paper_id"] for s in dti_in_a["sources"]} <= pa
    assert any(c["kind"] == "contradiction" for c in dti_in_a["comparisons"])


def test_citations_trace_to_stored_passages(env):
    client, a, _, _ = env
    res = investigate(client, a, DTI_Q)["result"]
    store = database.store_for(database.get_registry().get_project(a))
    rows = store.query("UNWIND $ids AS cid MATCH (p:Paper)-[:HAS_CHUNK]->(c:Chunk {id: cid}) "
                       "RETURN c.id AS id, p.id AS pid, c.page AS page, c.text AS text",
                       {"ids": [s["chunk_id"] for s in res["sources"]]})
    stored = {r["id"]: r for r in rows}
    for s in res["sources"]:
        assert s["chunk_id"] in stored and stored[s["chunk_id"]]["pid"] == s["paper_id"]
        assert stored[s["chunk_id"]]["page"] == s["page"]
    numbers = {s["n"] for s in res["sources"]}
    cited = ({n for f in res["findings"] for n in f["citations"]} | {n for g in res["gaps"] for n in g["citations"]}
             | {n for l in res["limitations"] for n in l["citations"]})
    assert cited <= numbers


def test_gaps_need_concrete_evidence_from_two_papers(env):
    client, a, b, _ = env
    for pid, q in ((a, DTI_Q), (b, "Which limitations of urban apiary studies remain open?")):
        res = investigate(client, pid, q)["result"]
        for g in res["gaps"]:
            assert g["support_papers"] >= 2 and len({e["paper_id"] for e in g["evidence"]}) >= 2, g
    bee_gaps = investigate(client, b, "Which limitations of urban apiary studies remain open?")["result"]["gaps"]
    # Both bee papers state that street-level colonies were not evaluated: a recurring, two-paper gap
    assert any(g["type"] == "recurring_limitation" for g in bee_gaps), bee_gaps


def test_saved_investigations_survive_restart_and_stay_in_their_project(env):
    client, a, b, _ = env
    done = investigate(client, a, DTI_Q)
    inv_id = done["id"]
    # Simulate an API restart: drop the in-memory manager and every cached connection.
    investigation_service._manager = None
    database.reset_store()
    again = client.get(f"/api/projects/{a}/investigations/{inv_id}")
    assert again.status_code == 200
    body = again.json()
    assert body["status"] == "completed" and body["project_id"] == a
    assert body["result"]["report_markdown"] == done["result"]["report_markdown"]
    assert [s["chunk_id"] for s in body["result"]["sources"]] == [s["chunk_id"] for s in done["result"]["sources"]]
    listed = client.get(f"/api/projects/{a}/investigations").json()
    assert inv_id in [i["id"] for i in listed["investigations"]] and listed["total"] >= 1
    # Not visible from the other project or the Default project
    assert client.get(f"/api/projects/{b}/investigations/{inv_id}").status_code == 404
    assert client.get(f"/api/investigations/{inv_id}").status_code == 404
    assert inv_id not in [i["id"] for i in client.get(f"/api/projects/{b}/investigations").json()["investigations"]]
    # Deleting a saved investigation
    assert client.delete(f"/api/projects/{b}/investigations/{inv_id}").status_code == 404
    assert client.delete(f"/api/projects/{a}/investigations/{inv_id}").status_code == 204
    assert client.get(f"/api/projects/{a}/investigations/{inv_id}").status_code == 404


def test_paper_deletion_is_scoped(env):
    client, a, b, _ = env
    pb = sorted(paper_ids(client, b))
    assert client.delete(f"/api/projects/{a}/papers/{pb[0]}").status_code == 404  # B's paper is not in A
    assert client.get(f"/api/projects/{a}/papers/{pb[0]}").status_code == 404
    assert client.get(f"/api/projects/{b}/papers/{pb[0]}").status_code == 200


def test_delete_project_requires_name_and_removes_everything(env):
    client, a, b, url = env
    from falkordb import FalkorDB
    graph = f"{BASE}__{b}"
    db = FalkorDB.from_url(url)
    assert graph in db.list_graphs()
    r = client.request("DELETE", f"/api/projects/{b}", json={"confirm_name": "urban bees"})
    assert r.status_code == 422  # must match exactly
    assert client.request("DELETE", "/api/projects/default", json={"confirm_name": "Default project"}).status_code == 403
    assert client.request("DELETE", f"/api/projects/{b}", json={"confirm_name": "Urban bees"}).status_code == 204
    assert graph not in db.list_graphs()
    assert client.get(f"/api/projects/{b}").status_code == 404
    assert client.get(f"/api/projects/{b}/papers").status_code == 404
    assert len(paper_ids(client, a)) == 3  # the other project is untouched
    db.close()
