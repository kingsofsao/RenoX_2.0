"""Graph writes, idempotency, paper isolation and research tools (requires FalkorDB)."""

from researchmind.pipeline import ingest_file
from researchmind.tools import ResearchTools


def test_ingest_counts(ingested, store):
    assert all(r["status"] == "ingested" for r in ingested)
    stats = store.stats()
    assert stats["Paper"] == 3
    assert stats["Chunk"] == sum(r["chunks"] for r in ingested)
    assert stats["Method"] >= 5 and stats["Dataset"] >= 4


def test_every_node_belongs_to_exactly_one_paper(ingested, store):
    """Methods, datasets and authors are per paper: no node is shared between two papers."""
    shared = store.query("""MATCH (p:Paper)-->(e) WHERE e:Method OR e:Dataset OR e:Author OR e:Chunk OR e:Page
                               OR e:Claim OR e:Finding OR e:Limitation
                            WITH e, count(DISTINCT p) AS owners WHERE owners > 1 RETURN count(e) AS n""")
    assert shared[0]["n"] == 0
    unowned = store.query("""MATCH (e) WHERE (e:Method OR e:Dataset OR e:Author) AND e.paper_id IS NULL
                             RETURN count(e) AS n""")
    assert unowned[0]["n"] == 0


def test_no_edges_between_papers(ingested, store):
    rows = store.query("""MATCH (a)-[r]-(b) WHERE a.paper_id IS NOT NULL AND b.paper_id IS NOT NULL
                            AND a.paper_id <> b.paper_id RETURN count(r) AS n""")
    assert rows[0]["n"] == 0
    rows = store.query("""MATCH (p:Paper)-[r]-(n) WHERE n.paper_id IS NOT NULL AND n.paper_id <> p.id
                          RETURN count(r) AS n""")
    assert rows[0]["n"] == 0
    assert store.query("MATCH ()-[r:CONTRADICTS|SIMILAR_TO|ADDRESSED_BY]->() RETURN count(r) AS n")[0]["n"] == 0


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


def test_search_evidence(ingested, store):
    res = ResearchTools(store).search_evidence("cold-start performance on unseen proteins", top_k=3)["results"]
    assert res and all(r["chunk_id"] and r["page"] >= 1 for r in res)
    assert any("Protein Language Models" in r["paper_title"] for r in res)


def test_explore_entity_stays_inside_one_paper(ingested, store):
    tools = ResearchTools(store)
    for p in tools.list_papers()["papers"]:
        scoped = ResearchTools(store, paper_ids=[p["id"]])
        out = scoped.explore_entity("Graph Attention Network")
        if "error" in out:
            continue
        for match in out["matches"]:
            assert [x["paper_id"] for x in match["papers"]] == [p["id"]]
            assert all(lim["chunk_id"].startswith(p["id"] + ":") for lim in match["limitations_of_papers_using_it"])
    gat = tools.explore_entity("GAT")["matches"]
    assert gat and all(m["entity"] == "Graph Attention Network" and len(m["papers"]) == 1 for m in gat)


def test_related_papers_finds_nothing_across_papers(ingested, store):
    tools = ResearchTools(store)
    pid = tools.list_papers()["papers"][0]["id"]
    related = tools.find_related_papers(pid)
    assert related["shared_entities"] == [] and related["statement_links"] == []


def test_compare_claims_within_a_paper(ingested, store):
    tools = ResearchTools(store)
    pid = next(p["id"] for p in tools.list_papers()["papers"] if "Graph Attention" in (p["title"] or ""))
    out = ResearchTools(store, paper_ids=[pid]).compare_claims("do graph models generalize to unseen proteins")
    assert list(out["statements_by_paper"]) and all(s["paper_id"] == pid for v in out["statements_by_paper"].values() for s in v)
    assert out["contradictions"] == []


def test_research_gaps_come_from_the_papers_own_limitations(ingested, store):
    tools = ResearchTools(store)
    for p in tools.list_papers()["papers"]:
        gaps = ResearchTools(store, paper_ids=[p["id"]]).find_research_gaps("cold-start")["gaps"]
        assert all(g["evidence"] and 0 < g["score"] <= 1 for g in gaps)
        assert all(e["chunk_id"].startswith(p["id"] + ":") for g in gaps for e in g["evidence"])


def test_graph_query_is_read_only(ingested, store):
    tools = ResearchTools(store)
    assert "error" in tools.graph_query("MATCH (n) DETACH DELETE n")
    assert "error" in tools.graph_query("CREATE (:Paper {id: 'x'})")
    rows = tools.graph_query("MATCH (p:Paper) RETURN p.title AS title")["rows"]
    assert len(rows) == 3
    assert "error" in ResearchTools(store, paper_ids=[tools.list_papers()["papers"][0]["id"]]).graph_query("MATCH (p) RETURN p")


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
