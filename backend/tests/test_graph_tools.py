"""Graph writes, idempotency and research tools (requires FalkorDB)."""

from researchmind.pipeline import ingest_file
from researchmind.tools import ResearchTools


def test_ingest_counts(ingested, store):
    assert all(r["status"] == "ingested" for r in ingested)
    stats = store.stats()
    assert stats["Paper"] == 3
    assert stats["Chunk"] == sum(r["chunks"] for r in ingested)
    assert stats["Method"] >= 5 and stats["Dataset"] == 4  # DAVIS, KIBA, BindingDB, PDBbind are shared nodes


def test_reingest_is_idempotent(ingested, store, sample_pdfs):
    before = store.stats()
    assert ingest_file(sample_pdfs[0], store, use_llm=False)["status"] == "unchanged"
    for p in sample_pdfs:
        assert ingest_file(p, store, use_llm=False, force=True)["status"] == "ingested"
    assert store.stats() == before


def test_evidence_links_point_to_pages(ingested, store):
    rows = store.query("""MATCH (s)-[:SUPPORTED_BY]->(c:Chunk) WHERE s:Claim OR s:Finding OR s:Limitation
                          RETURN count(s) AS n, min(c.page) AS lo""")
    assert rows[0]["n"] > 0 and rows[0]["lo"] >= 1
    orphans = store.query("""MATCH (s) WHERE (s:Claim OR s:Finding OR s:Limitation) AND NOT (s)-[:SUPPORTED_BY]->(:Chunk)
                             RETURN count(s) AS n""")
    assert orphans[0]["n"] == 0


def test_contradiction_detected(ingested, store):
    rows = store.query("MATCH (a)-[:CONTRADICTS]->(b) RETURN a.text AS a, b.text AS b")
    texts = " ".join(r["a"] + " " + r["b"] for r in rows).lower()
    assert "do not generalize" in texts and "generalize well" in texts


def test_search_evidence(ingested, store):
    res = ResearchTools(store).search_evidence("cold-start performance on unseen proteins", top_k=3)["results"]
    assert res and all(r["chunk_id"] and r["page"] >= 1 for r in res)
    assert any("Protein Language Models" in r["paper_title"] for r in res)


def test_explore_entity_multi_hop(ingested, store):
    out = ResearchTools(store).explore_entity("GAT")
    match = out["matches"][0]
    assert match["entity"] == "Graph Attention Network"
    assert len(match["papers"]) == 3
    assert match["limitations_of_papers_using_it"]


def test_related_papers_excludes_self(ingested, store):
    tools = ResearchTools(store)
    pid = tools.list_papers()["papers"][0]["id"]
    related = tools.find_related_papers(pid)
    assert related["shared_entities"]
    assert all(r["paper_id"] != pid for r in related["shared_entities"])


def test_compare_claims(ingested, store):
    out = ResearchTools(store).compare_claims("do graph models generalize to unseen proteins")
    assert len(out["statements_by_paper"]) >= 2
    assert out["contradictions"]


def test_research_gaps_have_evidence(ingested, store):
    gaps = ResearchTools(store).find_research_gaps("cold-start")["gaps"]
    types = {g["type"] for g in gaps}
    assert "conflicting_evidence" in types
    assert types & {"recurring_limitation", "unaddressed_limitation"}
    assert all(g["evidence"] and 0 < g["score"] <= 1 for g in gaps)


def test_graph_query_is_read_only(ingested, store):
    tools = ResearchTools(store)
    assert "error" in tools.graph_query("MATCH (n) DETACH DELETE n")
    assert "error" in tools.graph_query("CREATE (:Paper {id: 'x'})")
    rows = tools.graph_query("MATCH (p:Paper) RETURN p.title AS title")["rows"]
    assert len(rows) == 3


def test_pages_are_stored_and_linked(ingested, store):
    """Every page of every paper is a Page node with its text, and every chunk points to its page."""
    rows = store.query("""MATCH (p:Paper)-[:HAS_PAGE]->(pg:Page)
                          RETURN p.id AS id, p.num_pages AS num_pages, count(pg) AS pages, min(pg.number) AS first""")
    assert len(rows) == 3
    assert all(r["pages"] == r["num_pages"] and r["first"] == 1 for r in rows)
    unlinked = store.query("MATCH (c:Chunk) WHERE NOT (c)-[:ON_PAGE]->(:Page) RETURN count(c) AS n")
    assert unlinked[0]["n"] == 0
    mismatched = store.query("MATCH (c:Chunk)-[:ON_PAGE]->(pg:Page) WHERE c.page <> pg.number OR c.paper_id <> pg.paper_id RETURN count(c) AS n")
    assert mismatched[0]["n"] == 0
