"""INTEGRATION: account and paper isolation, saved investigations and evidence quality on a real FalkorDB.

Two accounts with deliberately unrelated papers:
  Alice = three synthetic drug-target papers      Bob = two synthetic urban-beekeeping papers
Neither account can reach the other's projects, papers or investigations, and an investigation of
one paper never retrieves evidence of any other paper - via the API, the MCP tools, vector search
or Cypher. Writes only to throwaway graphs `researchmind_pytest_proj*`, deleted afterwards.
No LLM is used (offline plan); see test_ollama_live.py for real models.
"""

import os

import pytest

from app import database
from app.main import app
from app.services import investigation_service
from authclient import Client, sign_up
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
    with Client(app) as alice, Client(app) as bob:
        for c in (alice, bob):
            c.get("/api/auth/csrf")
        _, _, a = sign_up(alice, email="alice@example.org", name="Alice Ball")
        _, _, b = sign_up(bob, email="bob@example.org", name="Bob Kahn")
        for client, pid, pdfs in ((alice, a, sample_pdfs), (bob, b, bees)):
            files = [("files", (p.name, p.read_bytes(), "application/pdf")) for p in pdfs]
            r = client.post(f"/api/projects/{pid}/papers/upload", files=files)
            assert r.json()["summary"]["processed"] == len(pdfs), r.text
        yield alice, bob, a, b, url
    database.reset_store()
    investigation_service._manager = None
    mp.undo()
    drop_graphs(url)


def papers(client, pid):
    return {p["id"]: p for p in client.get(f"/api/projects/{pid}/papers").json()["papers"]}


def paper_about(client, pid, word):
    return next(i for i, p in papers(client, pid).items() if word.lower() in (p["title"] or "").lower())


def investigate(client, pid, paper_id, question):
    r = client.post(f"/api/projects/{pid}/investigations", json={"question": question, "paper_id": paper_id, "wait": True})
    assert r.status_code == 200, r.text
    return r.json()


def test_each_account_sees_only_its_own_projects_and_papers(env):
    alice, bob, a, b, _ = env
    pa, pb = set(papers(alice, a)), set(papers(bob, b))
    assert len(pa) == 3 and len(pb) == 2 and not pa & pb
    assert [p["id"] for p in alice.get("/api/projects").json()["projects"]] == [a]
    assert [p["id"] for p in bob.get("/api/projects").json()["projects"]] == [b]
    for url in (f"/api/projects/{a}", f"/api/projects/{a}/papers", f"/api/projects/{a}/graph/overview",
                f"/api/projects/{a}/papers/{sorted(pa)[0]}", f"/api/projects/{a}/papers/{sorted(pa)[0]}/file"):
        assert bob.get(url).status_code == 404, url


def test_tools_cannot_reach_another_accounts_graph(env):
    alice, bob, a, b, _ = env
    pa, pb = set(papers(alice, a)), set(papers(bob, b))
    reg = database.get_registry()
    for owner_client, pid, own, other_question in ((alice, a, pa, BEE_Q), (bob, b, pb, DTI_Q)):
        owner = owner_client.get("/api/auth/me").json()["id"]
        tools = ResearchTools(database.store_for(reg.get_project(pid, owner)))
        mcp = MCPToolClient(tools)
        hits = mcp.call("search_evidence", {"query": other_question, "top_k": 15})["results"]
        assert {h["paper_id"] for h in hits} <= own  # vector + keyword search see only this account's project
        rows = mcp.call("graph_query", {"cypher": "MATCH (p:Paper) RETURN p.id AS id"})["rows"]
        assert {r["id"] for r in rows} == own  # even free-form Cypher is confined to the project graph


def test_an_investigation_reads_only_its_one_paper(env):
    alice, _, a, _, _ = env
    for paper_id in papers(alice, a):
        res = investigate(alice, a, paper_id, DTI_Q)
        assert res["paper_ids"] == [paper_id]
        r = res["result"]
        assert {s["paper_id"] for s in r["sources"]} <= {paper_id}
        assert {f["paper_id"] for f in r["findings"]} <= {paper_id}
        assert {g_e["paper_id"] for g in r["gaps"] for g_e in g["evidence"]} <= {paper_id}
        assert r["comparisons"] == []  # nothing is compared with other papers
        assert all(e["chunk_id"].startswith(paper_id + ":") for e in r["sources"])


def test_off_topic_paper_has_no_evidence(env):
    _, bob, _, b, _ = env
    bee = next(iter(papers(bob, b)))
    res = investigate(bob, b, bee, DTI_Q)["result"]
    assert res["evidence_found"] is False and res["sources"] == [] and res["confidence"]["level"] == "low"


def test_citations_trace_to_stored_passages(env):
    alice, _, a, _, _ = env
    paper_id = paper_about(alice, a, "graph attention")
    res = investigate(alice, a, paper_id, DTI_Q)["result"]
    owner = alice.get("/api/auth/me").json()["id"]
    store = database.store_for(database.get_registry().get_project(a, owner))
    rows = store.query("UNWIND $ids AS cid MATCH (p:Paper)-[:HAS_CHUNK]->(c:Chunk {id: cid}) "
                       "RETURN c.id AS id, p.id AS pid, c.page AS page",
                       {"ids": [s["chunk_id"] for s in res["sources"]]})
    stored = {r["id"]: r for r in rows}
    assert res["sources"]
    for s in res["sources"]:
        assert s["chunk_id"] in stored and stored[s["chunk_id"]]["pid"] == s["paper_id"] == paper_id
        assert stored[s["chunk_id"]]["page"] == s["page"]
    numbers = {s["n"] for s in res["sources"]}
    cited = ({n for f in res["findings"] for n in f["citations"]} | {n for g in res["gaps"] for n in g["citations"]}
             | {n for lim in res["limitations"] for n in lim["citations"]})
    assert cited <= numbers


def test_saved_investigations_survive_restart_and_stay_private(env):
    alice, bob, a, b, _ = env
    paper_id = paper_about(alice, a, "graph attention")
    done = investigate(alice, a, paper_id, DTI_Q)
    inv_id = done["id"]
    # Simulate an API restart: drop the in-memory manager and every cached connection.
    investigation_service._manager = None
    database.reset_store()
    again = alice.get(f"/api/projects/{a}/investigations/{inv_id}")
    assert again.status_code == 200
    body = again.json()
    assert body["status"] == "completed" and body["project_id"] == a and body["paper_ids"] == [paper_id]
    assert body["result"]["report_markdown"] == done["result"]["report_markdown"]
    listed = alice.get(f"/api/projects/{a}/investigations").json()
    assert inv_id in [i["id"] for i in listed["investigations"]]
    # Not visible to the other account, through any URL
    assert bob.get(f"/api/projects/{a}/investigations/{inv_id}").status_code == 404
    assert bob.get(f"/api/projects/{b}/investigations/{inv_id}").status_code == 404
    assert inv_id not in [i["id"] for i in bob.get(f"/api/projects/{b}/investigations").json()["investigations"]]
    assert bob.delete(f"/api/projects/{a}/investigations/{inv_id}").status_code == 404
    assert alice.delete(f"/api/projects/{a}/investigations/{inv_id}").status_code == 204
    assert alice.get(f"/api/projects/{a}/investigations/{inv_id}").status_code == 404


def test_paper_deletion_is_scoped(env):
    alice, bob, a, b, _ = env
    pb = sorted(papers(bob, b))
    assert alice.delete(f"/api/projects/{a}/papers/{pb[0]}").status_code == 404  # Bob's paper is not in Alice's project
    assert alice.delete(f"/api/projects/{b}/papers/{pb[0]}").status_code == 404  # nor can Alice reach Bob's project
    assert bob.get(f"/api/projects/{b}/papers/{pb[0]}").status_code == 200


def test_sessions_and_users_are_stored_safely(env):
    alice, _, _, _, url = env
    from falkordb import FalkorDB
    db = FalkorDB.from_url(url)
    reg = db.select_graph(f"{BASE}_registry")
    user = reg.ro_query("MATCH (u:User {email_lower: 'alice@example.org'}) RETURN u.password_hash").result_set[0][0]
    assert user.startswith("$argon2id$")
    token = alice.cookies.get("rm_session")
    stored = [r[0] for r in reg.ro_query("MATCH (s:Session) RETURN s.id").result_set]
    assert token not in stored and stored
    db.close()


def test_delete_account_removes_everything(env):
    alice, bob, a, b, url = env
    from falkordb import FalkorDB
    graph = f"{BASE}__{b}"
    db = FalkorDB.from_url(url)
    assert graph in db.list_graphs()
    assert bob.request("DELETE", "/api/auth/me", json={"password": "violet-harbour-lantern-42"}).status_code == 204
    assert graph not in db.list_graphs()
    assert bob.get("/api/auth/me").status_code == 401
    assert len(papers(alice, a)) == 3  # the other account is untouched
    db.close()
