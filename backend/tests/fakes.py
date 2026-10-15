"""In-memory stand-ins for the graph store and research tools, used by MOCKED tests.

FakeTools returns canned results shaped exactly like `researchmind.tools.ResearchTools`
over a three-paper corpus. `get_evidence` only knows the chunks below, so citation
verification is exercised for real: anything else is treated as non-existent evidence.
"""

from __future__ import annotations

import copy

P1, P2, P3 = "p_aaaaaaaaaaa1", "p_bbbbbbbbbbb2", "p_ccccccccccc3"
TITLES = {P1: "Graph Attention Networks for Drug-Target Interaction",
          P2: "Protein Language Models for Cold-Start Drug-Target Prediction",
          P3: "Structure-Aware GNNs for Binding Affinity"}

CHUNKS = {
    f"{P1}:c001": (P1, 1, "Abstract", "We propose a graph attention network (GAT) for drug-target interaction prediction on DAVIS and KIBA."),
    f"{P1}:c004": (P1, 2, "Results", "GAT models generalize well to unseen proteins, improving AUROC by 4% on DAVIS."),
    f"{P1}:c006": (P1, 2, "Limitations", "Our evaluation does not cover cold-start proteins with no known ligands."),
    f"{P2}:c002": (P2, 1, "Introduction", "Graph models do not generalize to unseen proteins in cold-start splits."),
    f"{P2}:c005": (P2, 3, "Results", "Protein language model embeddings improve cold-start AUROC by 9% over GAT baselines on BindingDB."),
    f"{P2}:c007": (P2, 4, "Limitations", "Future work should evaluate the approach on PDBbind affinity data."),
    f"{P3}:c003": (P3, 2, "Methods", "We train a structure-aware GNN on PDBbind complexes and compare against GAT."),
    f"{P3}:c006": (P3, 3, "Results", "Structure-aware GNNs outperform GAT on PDBbind but degrade on unseen protein families."),
    f"{P3}:c008": (P3, 4, "Limitations", "Our evaluation does not cover cold-start proteins without solved structures."),
}


def ev(cid: str) -> dict:
    pid, page, sect, text = CHUNKS[cid]
    return {"chunk_id": cid, "paper_id": pid, "paper_title": TITLES[pid], "year": 2024, "page": page, "section": sect, "text": text}


def stmt(cid: str, type_: str, relevance: float) -> dict:
    e = ev(cid)
    return {"id": cid + ":s", "type": type_, "text": e["text"], "polarity": 0, "paper_id": e["paper_id"],
            "paper_title": e["paper_title"], "year": 2024, "chunk_id": cid, "page": e["page"], "relevance": relevance}


class FakeStore:
    graph_name = "fake"

    def __init__(self, papers: bool = True):
        self._papers = papers

    def list_papers(self) -> list[dict]:
        if not self._papers:
            return []
        return [{"id": p, "title": t, "authors": [], "year": 2024, "source_file": f"{p}.pdf", "extractor": "heuristic", "chunks": 3}
                for p, t in TITLES.items()]

    def query(self, *a, **k):
        return []


class FakeTools:
    """Canned ResearchTools. `fail` names tools that raise; `calls` records every invocation."""

    def __init__(self, fail: set[str] | None = None, store: FakeStore | None = None):
        self.fail = fail or set()
        self.calls: list[tuple[str, dict]] = []
        self.store = store or FakeStore()

    def _enter(self, tool: str, **args):
        self.calls.append((tool, args))
        if tool in self.fail:
            raise RuntimeError(f"{tool} exploded (simulated tool failure)")

    def list_papers(self) -> dict:
        self._enter("list_papers")
        papers = self.store.list_papers()
        return {"count": len(papers), "papers": papers}

    def search_evidence(self, query: str, top_k: int = 6, paper_id: str | None = None) -> dict:
        self._enter("search_evidence", query=query, top_k=top_k, paper_id=paper_id)
        ids = [f"{P2}:c002", f"{P1}:c004", f"{P3}:c006", f"{P2}:c005", f"{P1}:c001"]
        rows = [{**ev(c), "statements": [], "score": round(0.9 - i * 0.05, 3)} for i, c in enumerate(ids)]
        if paper_id:
            rows = [r for r in rows if r["paper_id"] == paper_id]
        return {"query": query, "results": rows[: max(1, min(int(top_k), 15))]}

    def get_paper(self, paper_id: str) -> dict:
        self._enter("get_paper", paper_id=paper_id)
        if paper_id not in TITLES:
            return {"error": f"No paper with id {paper_id}. Use list_papers to see valid ids."}
        own = [c for c in CHUNKS if c.startswith(paper_id)]
        lim = [c for c in own if CHUNKS[c][2] == "Limitations"]
        res = [c for c in own if CHUNKS[c][2] == "Results"]
        return {"id": paper_id, "title": TITLES[paper_id], "authors": [], "year": 2024, "abstract": "", "source_file": "x.pdf", "num_pages": 4,
                "methods": [{"name": "Graph Attention Network", "entity_id": "graph-attention-network", "chunk_id": own[0], "page": CHUNKS[own[0]][1], "quote": "GAT"}],
                "datasets": [{"name": "DAVIS" if paper_id == P1 else "PDBbind", "entity_id": "d", "chunk_id": own[0], "page": CHUNKS[own[0]][1], "quote": "data"}],
                "claims": [],
                "findings": [{"id": c + ":f", "text": CHUNKS[c][3], "kind": None, "chunk_id": c, "page": CHUNKS[c][1], "section": "Results"} for c in res],
                "limitations": [{"id": c + ":l", "text": CHUNKS[c][3], "kind": "future_work" if "Future" in CHUNKS[c][3] else "limitation",
                                 "chunk_id": c, "page": CHUNKS[c][1], "section": "Limitations"} for c in lim]}

    def explore_entity(self, name: str, entity_type: str = "auto") -> dict:
        self._enter("explore_entity", name=name, entity_type=entity_type)
        if "gat" not in name.lower() and "attention" not in name.lower():
            return {"error": f"No method or dataset matching '{name}'. Try search_evidence instead."}
        papers = [{"paper_id": p, "title": TITLES[p], "year": 2024, "chunk_id": c, "quote": "GAT", "datasets": ["DAVIS"]}
                  for p, c in ((P1, f"{P1}:c001"), (P2, f"{P2}:c005"), (P3, f"{P3}:c003"))]
        return {"query": name, "matches": [{
            "entity": "Graph Attention Network", "type": "Method", "papers": papers,
            "statements_about_it": [{"type": "Finding", **{k: ev(f"{P1}:c004")[k] for k in ("text", "paper_title", "chunk_id", "page")}}],
            "limitations_of_papers_using_it": [{"text": CHUNKS[c][3], "kind": "limitation", "paper_title": TITLES[CHUNKS[c][0]], "chunk_id": c, "page": CHUNKS[c][1]}
                                               for c in (f"{P1}:c006", f"{P3}:c008")]}]}

    def find_related_papers(self, paper_id: str) -> dict:
        self._enter("find_related_papers", paper_id=paper_id)
        others = [p for p in TITLES if p != paper_id]
        return {"paper_id": paper_id,
                "shared_entities": [{"paper_id": p, "title": TITLES[p], "shared_entities": ["Method: Graph Attention Network"]} for p in others],
                "statement_links": [{"paper_id": P2, "title": TITLES[P2], "relation": "CONTRADICTS", "score": 0.81,
                                     "this_paper_statement": CHUNKS[f"{P1}:c004"][3], "this_chunk_id": f"{P1}:c004",
                                     "other_statement": CHUNKS[f"{P2}:c002"][3], "other_chunk_id": f"{P2}:c002"}]}

    def compare_claims(self, topic: str, top_k: int = 10) -> dict:
        self._enter("compare_claims", topic=topic, top_k=top_k)
        stmts = [stmt(f"{P2}:c002", "Claim", 0.88), stmt(f"{P1}:c004", "Finding", 0.86),
                 stmt(f"{P3}:c006", "Finding", 0.8), stmt(f"{P2}:c005", "Finding", 0.74)]
        by_paper: dict[str, list] = {}
        for s in stmts:
            by_paper.setdefault(s["paper_title"], []).append(s)
        a, b, c = ev(f"{P1}:c004"), ev(f"{P2}:c002"), ev(f"{P3}:c006")
        return {"topic": topic, "statements_by_paper": by_paper,
                "contradictions": [{"relation": "CONTRADICTS", "score": 0.81, "statement_a": a["text"], "paper_a": a["paper_title"], "chunk_a": a["chunk_id"],
                                    "statement_b": b["text"], "paper_b": b["paper_title"], "chunk_b": b["chunk_id"]}],
                "related_statements": [{"relation": "SIMILAR_TO", "score": 0.7, "statement_a": c["text"], "paper_a": c["paper_title"], "chunk_a": c["chunk_id"],
                                        "statement_b": b["text"], "paper_b": b["paper_title"], "chunk_b": b["chunk_id"]}]}

    def find_research_gaps(self, topic: str | None = None, max_gaps: int = 8) -> dict:
        self._enter("find_research_gaps", topic=topic, max_gaps=max_gaps)
        gaps = [
            {"id": "G1", "type": "recurring_limitation", "title": CHUNKS[f"{P1}:c006"][3],
             "rationale": "Reported as a limitation by 2 papers and not addressed by any ingested paper.", "score": 0.7,
             "evidence": [{"chunk_id": f"{P1}:c006", "paper": TITLES[P1], "page": 2, "quote": CHUNKS[f"{P1}:c006"][3]},
                          {"chunk_id": f"{P3}:c008", "paper": TITLES[P3], "page": 4, "quote": CHUNKS[f"{P3}:c008"][3]}]},
            {"id": "G2", "type": "conflicting_evidence", "title": "Resolve conflicting results on generalization to unseen proteins",
             "rationale": "Two papers report opposing results.", "score": 0.64,
             "evidence": [{"chunk_id": f"{P1}:c004", "paper": TITLES[P1], "page": 2, "quote": CHUNKS[f"{P1}:c004"][3]},
                          {"chunk_id": f"{P2}:c002", "paper": TITLES[P2], "page": 1, "quote": CHUNKS[f"{P2}:c002"][3]}]},
            # Evidence that does not exist in the graph: this gap must be dropped by verification.
            {"id": "G3", "type": "untested_combination", "title": "Phantom gap", "rationale": "No real evidence.", "score": 0.5,
             "evidence": [{"chunk_id": "p_deadbeef0000:c001", "paper": "Ghost paper", "page": 9, "quote": "invented"}]},
        ]
        return {"topic": topic, "note": "Candidate gaps are hypotheses.", "gaps": copy.deepcopy(gaps[:max_gaps])}

    def get_evidence(self, chunk_ids: list[str]) -> dict:
        self._enter("get_evidence", chunk_ids=chunk_ids)
        return {"evidence": [{k: v for k, v in ev(c).items() if k != "paper_id"} for c in list(chunk_ids)[:20] if c in CHUNKS]}

    def graph_query(self, cypher: str) -> dict:
        self._enter("graph_query", cypher=cypher)
        if "Method" in cypher:
            return {"rows": [{"name": "Graph Attention Network", "label": "Method"}, {"name": "DAVIS", "label": "Dataset"}]}
        return {"rows": []}
