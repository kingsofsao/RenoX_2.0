"""MOCKED tests for projects, saved investigations and evidence-quality rules (no database, no LLM).

The registry is the in-memory MemoryRegistry (conftest autouse fixture); each project gets its own
FakeStore/FakeTools so cross-project access can be checked at the API boundary. Real-database
isolation is covered by test_projects_integration.py.
"""

import time

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app import database
from app.main import app
from app.services import investigation_service
from app.services.investigation_service import InvestigationManager
from fakes import FakeStore, FakeTools
from researchmind.agent import Investigator
from researchmind.investigation import build_structured, inferences, open_questions
from researchmind.projects import MemoryRegistry, ProjectError

QUESTION = "Do graph attention models generalize to unseen proteins?"


@pytest.fixture
def api(memory_registry):
    stores: dict[str, FakeStore] = {}

    def store(project=Depends(database.get_project)):
        return stores.setdefault(project.id, FakeStore())
    manager = InvestigationManager(2, 30, investigator_factory=lambda s, use_llm=True, time_budget_s=None:
                                   Investigator(s, use_llm=False, tools=FakeTools(store=s)))
    app.dependency_overrides[database.get_store] = store
    app.dependency_overrides[investigation_service.get_manager] = lambda: manager
    yield TestClient(app), memory_registry, manager
    app.dependency_overrides.pop(database.get_store, None)
    app.dependency_overrides.pop(investigation_service.get_manager, None)


# ---------------------------------------------------------------------- project CRUD

def test_project_lifecycle(api):
    client, registry, _ = api
    listed = client.get("/api/projects").json()["projects"]
    assert [p["id"] for p in listed] == ["default"] and listed[0]["is_default"]
    created = client.post("/api/projects", json={"name": "  KidBrace   research ", "description": "Wearables"})
    assert created.status_code == 201
    p = created.json()
    assert p["name"] == "KidBrace research" and p["id"].startswith("prj_") and not p["is_default"]
    assert "graph" not in str(p) and "data_dir" not in p  # internals are never exposed
    assert client.post("/api/projects", json={"name": "kidbrace RESEARCH"}).status_code == 409  # case-insensitive unique
    assert client.post("/api/projects", json={"name": ""}).status_code == 422
    assert client.post("/api/projects", json={"name": "x" * 81}).status_code == 422
    renamed = client.patch(f"/api/projects/{p['id']}", json={"name": "KidBrace v2"}).json()
    assert renamed["name"] == "KidBrace v2" and renamed["updated_at"] >= p["updated_at"]
    assert client.patch("/api/projects/default", json={"name": "KidBrace v2"}).status_code == 409


def test_project_delete_safeguards(api):
    client, registry, _ = api
    pid = client.post("/api/projects", json={"name": "Temp"}).json()["id"]
    assert client.request("DELETE", f"/api/projects/{pid}", json={"confirm_name": "temp"}).status_code == 422
    assert client.request("DELETE", f"/api/projects/{pid}", json={}).status_code == 422
    r = client.request("DELETE", "/api/projects/default", json={"confirm_name": "Default project"})
    assert r.status_code == 403 and "cannot be deleted" in r.json()["error"]["message"]
    assert client.request("DELETE", f"/api/projects/{pid}", json={"confirm_name": "Temp"}).status_code == 204
    assert registry.dropped_graphs == [registry_graph(pid)]
    assert client.get(f"/api/projects/{pid}").status_code == 404


def registry_graph(pid):
    from researchmind.config import get_settings
    return f"{get_settings().graph_name}__{pid}"


@pytest.mark.parametrize("bad", ["prj_123", "../default", "PRJ_aaaaaaaaaa", "prj_zzzzzzzzzz"])
def test_unknown_or_malformed_project_ids_are_404(api, bad):
    client, _, _ = api
    r = client.get(f"/api/projects/{bad}/papers")
    assert r.status_code in (404, 422)


def test_unknown_project_is_404_not_500(api):
    client, _, _ = api
    r = client.get("/api/projects/prj_0123456789/papers")
    assert r.status_code == 404 and r.json()["error"]["code"] == "project_not_found"


def test_authorize_hides_other_owners_projects():
    reg = MemoryRegistry()
    p = reg.create_project("Mine", owner_id="alice")
    with pytest.raises(ProjectError) as e:
        reg.get_project(p.id, owner_id="bob")
    assert e.value.code == "not_found"
    assert reg.list_projects("bob") == []  # the Default project belongs to the local owner


# ---------------------------------------------------------------------- investigations per project

def wait_done(client, pid, inv_id):
    for _ in range(200):
        body = client.get(f"/api/projects/{pid}/investigations/{inv_id}").json()
        if body["status"] in ("completed", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("investigation did not finish")


def test_investigations_are_saved_and_scoped(api):
    client, registry, _ = api
    a = client.post("/api/projects", json={"name": "A"}).json()["id"]
    b = client.post("/api/projects", json={"name": "B"}).json()["id"]
    started = client.post(f"/api/projects/{a}/investigations", json={"question": QUESTION, "wait": False}).json()
    assert started["project_id"] == a
    done = wait_done(client, a, started["id"])
    assert done["status"] == "completed" and done["result"]["sources"]
    rec = registry.get_investigation(a, started["id"])
    assert rec["status"] == "completed" and rec["result_json"] and rec["question"] == QUESTION
    # other project / legacy default route cannot see it
    assert client.get(f"/api/projects/{b}/investigations/{started['id']}").status_code == 404
    assert client.get(f"/api/investigations/{started['id']}").status_code == 404
    assert client.get(f"/api/projects/{b}/investigations").json()["total"] == 0
    listed = client.get(f"/api/projects/{a}/investigations").json()
    assert listed["total"] == 1 and listed["investigations"][0]["id"] == started["id"]


def test_saved_result_is_served_after_restart(api):
    client, registry, manager = api
    pid = client.post("/api/projects", json={"name": "Persist"}).json()["id"]
    inv = client.post(f"/api/projects/{pid}/investigations", json={"question": QUESTION}).json()
    # "restart": a new manager with no in-memory jobs
    app.dependency_overrides[investigation_service.get_manager] = lambda: InvestigationManager(1, 30)
    again = client.get(f"/api/projects/{pid}/investigations/{inv['id']}").json()
    assert again["result"]["report_markdown"] == inv["result"]["report_markdown"]
    assert again["result"]["sources"] == inv["result"]["sources"] and again["progress"]


def test_interrupted_investigations_are_marked_failed():
    reg = MemoryRegistry()
    reg.ensure_default()
    reg.save_investigation({"id": "inv_aaaaaaaaaaaa", "project_id": "default", "question": "q", "status": "running",
                            "created_at": "2026-01-01T00:00:00+00:00"})
    assert reg.mark_interrupted() == 1
    rec = reg.get_investigation("default", "inv_aaaaaaaaaaaa")
    assert rec["status"] == "failed" and rec["error_code"] == "interrupted"
    from app.services.investigation_service import record_to_response
    assert record_to_response(rec)["error"]["code"] == "interrupted"


def test_project_with_running_investigation_cannot_be_deleted(api):
    client, _, manager = api
    pid = client.post("/api/projects", json={"name": "Busy"}).json()["id"]

    class Slow(FakeTools):
        def list_papers(self):
            time.sleep(0.6)
            return super().list_papers()
    manager.investigator_factory = lambda s, use_llm=True, time_budget_s=None: Investigator(s, use_llm=False, tools=Slow(store=s))
    client.post(f"/api/projects/{pid}/investigations", json={"question": QUESTION, "wait": False})
    assert client.request("DELETE", f"/api/projects/{pid}", json={"confirm_name": "Busy"}).status_code == 409


# ---------------------------------------------------------------------- evidence quality

class GapTools(FakeTools):
    """Gaps of every kind: only the two-paper, specific ones may be shown."""

    def find_research_gaps(self, topic=None, max_gaps=8):
        self._enter("find_research_gaps", topic=topic, max_gaps=max_gaps)
        from fakes import CHUNKS, P1, P2, TITLES
        ev = lambda c: {"chunk_id": c, "paper": TITLES[CHUNKS[c][0]], "page": CHUNKS[c][1], "quote": CHUNKS[c][3]}  # noqa: E731
        return {"topic": topic, "gaps": [
            {"id": "G1", "type": "recurring_limitation", "title": "Cold-start proteins are not evaluated", "rationale": "2 papers.",
             "score": 0.8, "specific": True, "evidence": [ev(f"{P1}:c006"), ev("p_ccccccccccc3:c008")]},
            {"id": "G2", "type": "unaddressed_limitation", "title": "Single paper limitation", "rationale": "1 paper.",
             "score": 0.7, "specific": True, "evidence": [ev(f"{P2}:c007")]},
            {"id": "G3", "type": "recurring_limitation", "title": "It helps to minimize this in the future", "rationale": "generic",
             "score": 0.9, "specific": False, "evidence": [ev(f"{P1}:c006"), ev("p_ccccccccccc3:c008")]},
        ]}


def test_only_specific_multi_paper_gaps_are_reported():
    inv = Investigator(FakeStore(), use_llm=False, tools=GapTools())
    result = inv.run(QUESTION)
    s = build_structured(result, lambda ids: inv.tools.get_evidence(ids)["evidence"], corpus_size=3)
    assert [g["title"] for g in s["gaps"]] == ["Cold-start proteins are not evaluated"]
    assert s["gaps"][0]["support_papers"] == 2 and s["gaps"][0]["id"] == "G1"


def test_specificity_rules():
    from researchmind.tools import is_specific_limitation, valid_entity
    assert is_specific_limitation("Our evaluation is limited to kinase targets from DAVIS and BindingDB.")
    assert is_specific_limitation("We did not evaluate colonies at street level.")
    assert not is_specific_limitation("It, therefore, helps to minimize this tragedy to reoccur in the future.")
    assert not is_specific_limitation("This comprehensive review offers valuable insights into the current state.")
    assert valid_entity("PlantVillage") and valid_entity("Graph Attention Network")
    assert not any(valid_entity(n) for n in ("THE DATASET", "Crop", "Stavness This", "Challenges Small"))


def test_findings_inferences_and_open_questions_are_separated():
    md = ("# Investigation: q\n\n## Answer\nX [1].\n## Candidate research gaps\n- Hypothesis: combine A and B [1, 2].\n"
          "- [Hypothesis:] test on street-level hives [3]\n- not a hypothesis line\n"
          "## Not covered by the evidence\n- Costs of the device.\n- None\n## Confidence\nLow.")
    assert inferences(md) == [{"text": "combine A and B [1, 2].", "citations": [1, 2]},
                              {"text": "test on street-level hives [3]", "citations": [3]}]
    assert open_questions(md, True, "q") == ["Costs of the device."]
    assert open_questions("", False, "What about cake?") == ["What about cake?"]
