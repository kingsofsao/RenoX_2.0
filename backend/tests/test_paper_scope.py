"""Investigations limited to the papers the user selected.

MOCKED tests run without a database; the `ingested` tests need FalkorDB and check that every
scoped tool only returns evidence from the selected papers.
"""

import pytest

from app import database
from app.main import app
from app.services import investigation_service
from app.services.investigation_service import InvestigationManager
from authclient import sign_up
from fakes import CHUNKS, P1, P2, FakeStore, FakeTools
from researchmind.agent import Investigator
from researchmind.tools import ResearchTools

QUESTION = "Do graph attention models generalize to unseen proteins?"


class RecordingStore(FakeStore):
    """FakeStore that answers chunk lookups for every paper, so scope filtering is visible."""

    def query(self, cypher, params=None, **k):
        ids = (params or {}).get("ids") or []
        return [{"chunk_id": c, "paper_title": "t", "year": 2024, "page": 1, "section": "s", "text": "x"}
                for c in ids if c in CHUNKS]


def test_scoped_tools_hide_other_papers():
    tools = ResearchTools(RecordingStore(), paper_ids=[P1])
    assert [p["id"] for p in tools.list_papers()["papers"]] == [P1]
    assert "error" in tools.get_paper(P2)
    assert "error" in tools.find_related_papers(P2)
    assert "error" in tools.graph_query("MATCH (p:Paper) RETURN p.title")
    rows = tools.get_evidence([f"{P1}:c001", f"{P2}:c002"])["evidence"]
    assert [r["chunk_id"] for r in rows] == [f"{P1}:c001"]


def test_unscoped_tools_see_the_whole_library():
    tools = ResearchTools(RecordingStore())
    assert tools.scope is None and len(tools.list_papers()["papers"]) == 3
    assert len(tools.get_evidence([f"{P1}:c001", f"{P2}:c002"])["evidence"]) == 2


def test_scope_note_names_only_the_selected_papers():
    inv = Investigator(RecordingStore(), use_llm=False, tools=ResearchTools(RecordingStore(), paper_ids=[P1]))
    note = inv.scope_note()
    assert P1 in note and P2 not in note and "ONLY" in note
    assert Investigator(RecordingStore(), use_llm=False, tools=FakeTools()).scope_note() == ""


@pytest.fixture
def api():
    seen = []

    def factory(store, use_llm=True, time_budget_s=None, paper_ids=None, **kw):
        seen.append(paper_ids)
        return Investigator(store, use_llm=False, tools=FakeTools(), time_budget_s=time_budget_s)

    database.reset_store()
    manager = InvestigationManager(2, 30, investigator_factory=factory)
    app.dependency_overrides[database.get_store] = lambda: FakeStore()
    app.dependency_overrides[investigation_service.get_manager] = lambda: manager
    client, _, pid = sign_up()
    yield client, seen, f"/api/projects/{pid}/investigations"
    app.dependency_overrides.pop(database.get_store, None)
    app.dependency_overrides.pop(investigation_service.get_manager, None)
    database.reset_store()


def test_api_analyses_exactly_the_selected_paper_and_saves_it(api):
    client, seen, url = api
    r = client.post(url, json={"question": QUESTION, "paper_id": P1, "wait": True})
    assert r.status_code == 200, r.text
    assert seen == [[P1]] and r.json()["paper_ids"] == [P1]
    assert any("Analysing one paper" in e["message"] for e in r.json()["progress"])
    saved = client.get(f"{url}/{r.json()['id']}").json()
    assert saved["paper_ids"] == [P1] and saved["paper_title"]


def test_api_has_no_whole_library_mode(api):
    client, seen, url = api
    for body in ({"question": QUESTION}, {"question": QUESTION, "paper_id": None},
                 {"question": QUESTION, "paper_ids": [P1, P2]}):
        assert client.post(url, json=body).status_code == 422
    assert seen == []


def test_api_rejects_unknown_paper(api):
    client, seen, url = api
    r = client.post(url, json={"question": QUESTION, "paper_id": "p_000000000000"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "paper_not_found"
    assert seen == []


def test_confidence_for_one_selected_paper():
    from researchmind.investigation import assess_confidence
    args = dict(mode="llm", findings=[{}], comparisons=[], sources=[{}] * 4, papers=1, corpus_size=1, unverified=0)
    scoped = assess_confidence(**args, scoped=True)
    assert scoped["level"] != "low"  # one paper is all that was asked for
    assert any("1 selected paper" in u for u in scoped["uncertainties"])
    assert assess_confidence(**args)["level"] == "low"  # a whole library that holds only one paper


def test_report_language_instruction():
    inv = Investigator(RecordingStore(), use_llm=False, tools=FakeTools(), language="de")
    note = inv.language_note()
    assert "German" in note and "Hypothesis:" in note and "English" in note
    assert Investigator(RecordingStore(), use_llm=False, tools=FakeTools()).language_note() == ""
    assert Investigator(RecordingStore(), use_llm=False, tools=FakeTools(), language="xx").language == "en"


# ---------------------------------------------------------------------- FalkorDB

def _papers_in(output) -> set[str]:
    """Paper ids behind every chunk id anywhere in a tool result."""
    found = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("chunk_id", "chunk_a", "chunk_b", "this_chunk_id", "other_chunk_id") and isinstance(v, str):
                    found.add(v.split(":", 1)[0])
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(output)
    return found


def test_scoped_tools_return_only_selected_paper(ingested, store):
    papers = store.list_papers()
    target = papers[0]["id"]
    tools = ResearchTools(store, paper_ids=[target])
    q = "generalization to unseen proteins in cold-start drug-target prediction"
    outputs = [tools.search_evidence(q, top_k=8), tools.compare_claims(q), tools.find_research_gaps(q),
               tools.get_paper(target), tools.find_related_papers(target)]
    for name in ("Graph Attention Network", "DAVIS", "PDBbind"):
        outputs.append(tools.explore_entity(name))
    assert tools.search_evidence(q, top_k=8)["results"], "the selected paper should still have evidence"
    for out in outputs:
        assert _papers_in(out) <= {target}, out
    assert {r["paper_id"] for r in tools.explore_entity("DAVIS").get("matches", [{}])[0].get("papers", [])} <= {target}


def test_offline_investigation_scoped_to_one_paper(ingested, store):
    target = store.list_papers()[0]["id"]
    result = Investigator(store, use_llm=False, paper_ids=[target]).run(QUESTION)
    assert all(r["chunk_id"].startswith(target + ":") for r in result.references)


def test_confidence_for_one_selected_paper():
    from researchmind.investigation import assess_confidence
    args = dict(mode="llm", findings=[{}], comparisons=[], sources=[{}] * 4, papers=1, corpus_size=1, unverified=0)
    scoped = assess_confidence(**args, scoped=True)
    assert scoped["level"] != "low"  # one paper is all that was asked for
    assert any("1 selected paper" in u for u in scoped["uncertainties"])
    assert assess_confidence(**args)["level"] == "low"  # the whole library has only one paper


def test_broad_question_about_one_paper_still_reaches_the_ai():
    """'What limitations do the authors acknowledge?' matches no passage closely, but the chosen paper answers it:
    the AI must get that paper's own limitations and findings instead of a 'no evidence' refusal."""
    from researchmind.investigation import build_structured
    from test_investigation_mocked import OffTopicTools
    from test_llm_providers import ScriptedChat, report
    tools = OffTopicTools()
    tools.scope = [P1]
    llm = ScriptedChat([report("S1")])
    inv = Investigator(RecordingStore(), llm=llm, tools=tools, require_llm=True)
    result = inv.run("What limitations do the authors acknowledge?")
    assert llm.requests and result.mode == "llm"
    prompt = llm.requests[0]["messages"][-1]["content"]
    assert "Our evaluation does not cover cold-start proteins" in prompt  # the paper's own limitation was provided
    s = build_structured(result, lambda ids: tools.get_evidence(ids)["evidence"], corpus_size=1, scoped=True, paper_ids=[P1])
    assert s["evidence_found"] and s["sources"]
    assert {x["paper_id"] for x in s["sources"]} == {P1}


def test_report_language_reaches_the_system_prompt():
    from test_llm_providers import ScriptedChat, report
    tools = FakeTools()
    tools.scope = [P1]
    llm = ScriptedChat([report("S1")])
    Investigator(RecordingStore(), llm=llm, tools=tools, language="ta").run(QUESTION)
    system = llm.requests[0]["messages"][0]["content"]
    assert "OUTPUT LANGUAGE: Tamil (தமிழ்)" in system
