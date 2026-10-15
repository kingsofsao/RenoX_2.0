"""Research tools over the FalkorDB knowledge graph.

These functions are the single implementation behind both the MCP server
(`researchmind.mcp_server`) and the investigation agent (`researchmind.agent`).
Every result that makes a factual statement carries `chunk_id` evidence so the
agent can cite the exact page it came from.
"""

from __future__ import annotations

import re
from typing import Any

from .embeddings import get_embedder, jaccard
from .extract import slug
from .graph import GraphStore

MAX_TEXT = 500


def _trim(text: str | None, n: int = MAX_TEXT) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _fulltext_query(text: str) -> str:
    terms = [t for t in re.findall(r"[A-Za-z0-9]{3,}", text)][:12]
    return "|".join(terms)


class ResearchTools:
    def __init__(self, store: GraphStore):
        self.store = store

    # ------------------------------------------------------------------ catalogue
    def list_papers(self) -> dict:
        papers = self.store.list_papers()
        return {"count": len(papers), "papers": papers}

    def get_paper(self, paper_id: str) -> dict:
        q = self.store.query
        meta = q("""MATCH (p:Paper {id: $id}) RETURN p.id AS id, p.title AS title, p.authors AS authors, p.year AS year,
                    p.abstract AS abstract, p.source_file AS source_file, p.num_pages AS num_pages""", {"id": paper_id}, read_only=True)
        if not meta:
            return {"error": f"No paper with id {paper_id}. Use list_papers to see valid ids."}
        out = meta[0]
        out["abstract"] = _trim(out["abstract"], 800)
        for key, rel in (("methods", "USES_METHOD"), ("datasets", "USES_DATASET")):
            out[key] = q(f"""MATCH (p:Paper {{id: $id}})-[r:{rel}]->(e) OPTIONAL MATCH (c:Chunk {{id: r.chunk_id}})
                             RETURN e.name AS name, e.id AS entity_id, r.chunk_id AS chunk_id, c.page AS page, r.quote AS quote""",
                         {"id": paper_id}, read_only=True)
        for key, rel in (("claims", "MAKES_CLAIM"), ("findings", "REPORTS_FINDING"), ("limitations", "HAS_LIMITATION")):
            out[key] = q(f"""MATCH (p:Paper {{id: $id}})-[:{rel}]->(s)-[:SUPPORTED_BY]->(c:Chunk)
                             RETURN s.id AS id, s.text AS text, s.kind AS kind, c.id AS chunk_id, c.page AS page, c.section AS section""",
                         {"id": paper_id}, read_only=True)
        return out

    # ------------------------------------------------------------------ retrieval
    def search_evidence(self, query: str, top_k: int = 6, paper_id: str | None = None) -> dict:
        """Hybrid semantic (vector index) + keyword (full-text index) search over evidence chunks."""
        top_k = max(1, min(int(top_k), 15))
        vec = get_embedder().encode([query])[0].tolist()
        scores: dict[str, float] = {}
        for row in self.store.query(
                "CALL db.idx.vector.queryNodes('Chunk', 'embedding', $k, vecf32($vec)) YIELD node, score "
                "RETURN node.id AS id, node.paper_id AS paper_id, 1 - score AS sim",
                {"k": top_k * 3, "vec": vec}, read_only=True):
            if paper_id and row["paper_id"] != paper_id:
                continue
            scores[row["id"]] = float(row["sim"])
        ft = _fulltext_query(query)
        if ft:
            try:
                rows = self.store.query(
                    "CALL db.idx.fulltext.queryNodes('Chunk', $q) YIELD node, score "
                    "RETURN node.id AS id, node.paper_id AS paper_id, score LIMIT $k",
                    {"q": ft, "k": top_k * 3}, read_only=True)
            except Exception:
                rows = []
            best = max((float(r["score"]) for r in rows), default=0) or 1.0
            for r in rows:
                if paper_id and r["paper_id"] != paper_id:
                    continue
                # keyword hits add a bounded bonus on top of semantic similarity
                scores[r["id"]] = scores.get(r["id"], 0.0) + 0.25 * float(r["score"]) / best

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        if not ranked:
            return {"query": query, "results": []}
        rows = self.store.query(
            """UNWIND $ids AS cid MATCH (p:Paper)-[:HAS_CHUNK]->(c:Chunk {id: cid})
               OPTIONAL MATCH (s)-[:SUPPORTED_BY]->(c)
               RETURN c.id AS chunk_id, p.id AS paper_id, p.title AS paper_title, p.year AS year, c.page AS page,
                      c.section AS section, c.text AS text,
                      collect(CASE WHEN s IS NULL THEN NULL ELSE {type: labels(s)[0], text: s.text} END) AS statements""",
            {"ids": [cid for cid, _ in ranked]}, read_only=True)
        by_id = {r["chunk_id"]: r for r in rows}
        results = []
        for cid, score in ranked:
            r = by_id.get(cid)
            if r:
                r["text"] = _trim(r["text"])
                r["statements"] = [s for s in r["statements"] if s][:5]
                r["score"] = round(score, 3)
                results.append(r)
        return {"query": query, "results": results}

    def get_evidence(self, chunk_ids: list[str]) -> dict:
        rows = self.store.query(
            """UNWIND $ids AS cid MATCH (p:Paper)-[:HAS_CHUNK]->(c:Chunk {id: cid})
               RETURN c.id AS chunk_id, p.title AS paper_title, p.year AS year, c.page AS page, c.section AS section, c.text AS text""",
            {"ids": list(chunk_ids)[:20]}, read_only=True)
        return {"evidence": rows}

    # ------------------------------------------------------------------ graph traversal
    def _resolve_entity(self, name: str, entity_type: str) -> list[dict]:
        labels = ["Method", "Dataset"] if entity_type == "auto" else [entity_type.capitalize()]
        key = slug(name)
        found = []
        for label in labels:
            rows = self.store.query(f"MATCH (e:{label}) RETURN e.id AS id, e.name AS name", read_only=True)
            exact = [r for r in rows if r["id"] == key]
            fuzzy = [] if exact else [r for r in rows if key in r["id"] or r["id"] in key or jaccard(name, r["name"]) >= 0.5]
            found += [{**r, "label": label} for r in exact + fuzzy]
        if any(f["id"] == key for f in found):
            found = [f for f in found if f["id"] == key]
        return found[:3]

    def explore_entity(self, name: str, entity_type: str = "auto") -> dict:
        """Multi-hop: Method/Dataset -> papers -> their findings, datasets/methods, limitations."""
        matches = self._resolve_entity(name, entity_type)
        if not matches:
            return {"error": f"No method or dataset matching '{name}'. Try search_evidence instead."}
        out = []
        for m in matches:
            rel, other_rel, other_label = (("USES_METHOD", "USES_DATASET", "datasets") if m["label"] == "Method"
                                           else ("USES_DATASET", "USES_METHOD", "methods"))
            papers = self.store.query(
                f"""MATCH (p:Paper)-[r:{rel}]->(e {{id: $id}})
                    OPTIONAL MATCH (p)-[:{other_rel}]->(o)
                    RETURN p.id AS paper_id, p.title AS title, p.year AS year, r.chunk_id AS chunk_id, r.quote AS quote,
                           collect(DISTINCT o.name) AS {other_label}""", {"id": m["id"]}, read_only=True)
            link = "ABOUT_METHOD" if m["label"] == "Method" else "EVALUATED_ON"
            statements = self.store.query(
                f"""MATCH (p:Paper)-[]->(s)-[:{link}]->(e {{id: $id}}) MATCH (s)-[:SUPPORTED_BY]->(c:Chunk)
                    RETURN labels(s)[0] AS type, s.text AS text, p.title AS paper_title, c.id AS chunk_id, c.page AS page""",
                {"id": m["id"]}, read_only=True)
            limitations = self.store.query(
                f"""MATCH (p:Paper)-[:{rel}]->(e {{id: $id}}) MATCH (p)-[:HAS_LIMITATION]->(l)-[:SUPPORTED_BY]->(c:Chunk)
                    RETURN l.text AS text, l.kind AS kind, p.title AS paper_title, c.id AS chunk_id, c.page AS page""",
                {"id": m["id"]}, read_only=True)
            out.append({"entity": m["name"], "type": m["label"], "papers": papers,
                        "statements_about_it": statements, "limitations_of_papers_using_it": limitations})
        return {"query": name, "matches": out}

    def find_related_papers(self, paper_id: str) -> dict:
        """Papers connected to this one via shared methods/datasets or similar/contradicting statements."""
        shared = self.store.query(
            """MATCH (a:Paper {id: $id})-[:USES_METHOD|USES_DATASET]->(e)<-[:USES_METHOD|USES_DATASET]-(b:Paper)
               WHERE b.id <> $id
               RETURN b.id AS paper_id, b.title AS title, collect(DISTINCT labels(e)[0] + ': ' + e.name) AS shared_entities""",
            {"id": paper_id}, read_only=True)
        statement_links = self.store.query(
            """MATCH (a:Paper {id: $id})-[]->(s)-[x:SIMILAR_TO|CONTRADICTS|ADDRESSED_BY]-(t)<-[]-(b:Paper)
               WHERE b.id <> $id AND (t:Claim OR t:Finding OR t:Limitation)
               MATCH (s)-[:SUPPORTED_BY]->(cs:Chunk) MATCH (t)-[:SUPPORTED_BY]->(ct:Chunk)
               RETURN b.id AS paper_id, b.title AS title, type(x) AS relation, x.score AS score,
                      s.text AS this_paper_statement, cs.id AS this_chunk_id, t.text AS other_statement, ct.id AS other_chunk_id
               ORDER BY score DESC LIMIT 20""", {"id": paper_id}, read_only=True)
        return {"paper_id": paper_id, "shared_entities": shared, "statement_links": statement_links}

    def compare_claims(self, topic: str, top_k: int = 10) -> dict:
        """Collect claims/findings on a topic across papers and surface agreements and contradictions."""
        top_k = max(2, min(int(top_k), 20))
        vec = get_embedder().encode([topic])[0].tolist()
        hits: dict[str, float] = {}
        for label in ("Claim", "Finding"):
            for r in self.store.query(
                    f"CALL db.idx.vector.queryNodes('{label}', 'embedding', $k, vecf32($vec)) YIELD node, score "
                    "RETURN node.id AS id, 1 - score AS sim", {"k": top_k, "vec": vec}, read_only=True):
                hits[r["id"]] = float(r["sim"])
        ids = [i for i, _ in sorted(hits.items(), key=lambda kv: kv[1], reverse=True)[:top_k]]
        statements = self.store.query(
            """UNWIND $ids AS sid MATCH (p:Paper)-[]->(s {id: sid})-[:SUPPORTED_BY]->(c:Chunk)
               RETURN s.id AS id, labels(s)[0] AS type, s.text AS text, s.polarity AS polarity,
                      p.id AS paper_id, p.title AS paper_title, p.year AS year, c.id AS chunk_id, c.page AS page""",
            {"ids": ids}, read_only=True)
        for s in statements:
            s["relevance"] = round(hits.get(s["id"], 0), 3)
        relations = self.store.query(
            """UNWIND $ids AS sid MATCH (a {id: sid})-[x:CONTRADICTS|SIMILAR_TO]->(b)
               MATCH (a)-[:SUPPORTED_BY]->(ca:Chunk) MATCH (b)-[:SUPPORTED_BY]->(cb:Chunk)
               MATCH (pa:Paper)-[]->(a) MATCH (pb:Paper)-[]->(b)
               RETURN type(x) AS relation, x.score AS score, a.text AS statement_a, pa.title AS paper_a, ca.id AS chunk_a,
                      b.text AS statement_b, pb.title AS paper_b, cb.id AS chunk_b
               ORDER BY relation, score DESC""", {"ids": ids}, read_only=True)
        by_paper: dict[str, list] = {}
        for s in sorted(statements, key=lambda s: -s["relevance"]):
            by_paper.setdefault(s["paper_title"], []).append(s)
        return {"topic": topic, "statements_by_paper": by_paper,
                "contradictions": [r for r in relations if r["relation"] == "CONTRADICTS"],
                # SIMILAR_TO means "about the same thing", not necessarily agreement - the agent judges that
                "related_statements": [r for r in relations if r["relation"] == "SIMILAR_TO"]}

    # ------------------------------------------------------------------ gaps
    def find_research_gaps(self, topic: str | None = None, max_gaps: int = 8) -> dict:
        """Candidate research gaps derived from graph structure, each with supporting evidence."""
        gaps: list[dict[str, Any]] = []
        relevance = self._topic_relevance(topic) if topic else None

        # 1. Limitations / future work that no other paper addresses (recurring ones rank higher)
        rows = self.store.query(
            """MATCH (p:Paper)-[:HAS_LIMITATION]->(l:Limitation)-[:SUPPORTED_BY]->(c:Chunk)
               OPTIONAL MATCH (l)-[a:ADDRESSED_BY]->(addr)<-[]-(ap:Paper)
               OPTIONAL MATCH (l)-[:SIMILAR_TO]-(l2:Limitation)<-[:HAS_LIMITATION]-(p2:Paper)-[:HAS_CHUNK]->(c2:Chunk)<-[:SUPPORTED_BY]-(l2)
               RETURN l.id AS id, l.text AS text, l.kind AS kind, p.title AS paper_title, c.id AS chunk_id, c.page AS page,
                      collect(DISTINCT {text: addr.text, paper: ap.title}) AS addressed_by,
                      collect(DISTINCT {text: l2.text, paper: p2.title, chunk_id: c2.id, page: c2.page}) AS recurring""", read_only=True)
        seen_recurring: set[str] = set()
        for r in rows:
            if r["id"] in seen_recurring:
                continue
            addressed = [a for a in r["addressed_by"] if a.get("text")]
            recurring = [x for x in r["recurring"] if x.get("text")]
            if addressed:
                continue  # some other paper already reports work on this
            seen_recurring.update(x.get("chunk_id", "") for x in recurring)
            for x in recurring:
                seen_recurring.update(l2["id"] for l2 in rows if l2["chunk_id"] == x["chunk_id"] and l2["text"] == x["text"])
            evidence = [{"chunk_id": r["chunk_id"], "paper": r["paper_title"], "page": r["page"], "quote": r["text"]}]
            evidence += [{"chunk_id": x["chunk_id"], "paper": x["paper"], "page": x.get("page"), "quote": x["text"]} for x in recurring]
            score = 0.5 + 0.2 * len(recurring) + (0.1 if r["kind"] == "future_work" else 0)
            gaps.append({
                "type": "recurring_limitation" if recurring else ("open_future_work" if r["kind"] == "future_work" else "unaddressed_limitation"),
                "title": _trim(r["text"], 160),
                "rationale": (f"Reported as a limitation by {1 + len(recurring)} papers and not addressed by any ingested paper."
                              if recurring else "Stated by the authors and not addressed by any other ingested paper."),
                "evidence": evidence, "score": round(score, 2), "_text": r["text"]})

        # 2. Contradictory evidence between papers (one gap per paper pair, strongest conflict first)
        pairs: dict[frozenset, list[dict]] = {}
        for r in self.store.query(
                """MATCH (a)-[x:CONTRADICTS]->(b) MATCH (pa:Paper)-[]->(a)-[:SUPPORTED_BY]->(ca:Chunk)
                   MATCH (pb:Paper)-[]->(b)-[:SUPPORTED_BY]->(cb:Chunk)
                   RETURN a.text AS a, b.text AS b, pa.title AS pa, pb.title AS pb, ca.id AS ca, cb.id AS cb, ca.page AS pga, cb.page AS pgb, x.score AS score
                   ORDER BY score DESC LIMIT 30""", read_only=True):
            pairs.setdefault(frozenset((r["pa"], r["pb"])), []).append(r)
        for conflicts in pairs.values():
            top = conflicts[0]
            evidence, seen_chunks = [], set()
            for r in conflicts[:2]:
                for cid, paper, page, quote in ((r["ca"], r["pa"], r["pga"], r["a"]), (r["cb"], r["pb"], r["pgb"], r["b"])):
                    if (cid, quote) not in seen_chunks:
                        seen_chunks.add((cid, quote))
                        evidence.append({"chunk_id": cid, "paper": paper, "page": page, "quote": quote})
            gaps.append({
                "type": "conflicting_evidence",
                "title": f"Resolve conflicting results: {_trim(top['a'], 90)}",
                "rationale": (f"'{top['pa']}' and '{top['pb']}' report opposing results on closely related statements "
                              f"({len(conflicts)} conflicting statement pair(s)); a controlled comparison under shared evaluation settings is missing."),
                "evidence": evidence,
                "score": round(0.6 + 0.3 * float(top["score"]), 2), "_text": top["a"] + " " + top["b"]})

        # 3. Untested method x dataset combinations among connected papers
        combos = self.store.query(
            """MATCH (p1:Paper)-[r1:USES_METHOD]->(m:Method), (p2:Paper)-[r2:USES_DATASET]->(d:Dataset)
               WHERE NOT (m)<-[:USES_METHOD]-(:Paper)-[:USES_DATASET]->(d)
               WITH m, d, collect(DISTINCT p1.title) AS mp, collect(DISTINCT p2.title) AS dp,
                    collect(DISTINCT {chunk_id: r1.chunk_id, paper: p1.title, quote: r1.quote})[0..1] AS me,
                    collect(DISTINCT {chunk_id: r2.chunk_id, paper: p2.title, quote: r2.quote})[0..1] AS de
               WHERE size(mp) >= 2 OR size(dp) >= 2
               RETURN m.name AS method, d.name AS dataset, size(mp) AS method_papers, size(dp) AS dataset_papers, me, de
               ORDER BY method_papers + dataset_papers DESC LIMIT 4""", read_only=True)
        for c in combos:
            gaps.append({
                "type": "untested_combination",
                "title": f"Evaluate {c['method']} on {c['dataset']}",
                "rationale": (f"{c['method']} appears in {c['method_papers']} papers and {c['dataset']} in {c['dataset_papers']}, "
                              "but no ingested paper evaluates them together."),
                "evidence": c["me"] + c["de"], "score": round(0.35 + 0.05 * (c["method_papers"] + c["dataset_papers"]), 2),
                "_text": f"{c['method']} {c['dataset']}"})

        if relevance:
            for g in gaps:
                g["score"] = round(g["score"] * (0.4 + relevance(g["_text"])), 3)
        for g in gaps:
            g["score"] = min(1.0, g["score"])
        gaps.sort(key=lambda g: g["score"], reverse=True)
        for i, g in enumerate(gaps[:max_gaps], start=1):
            g["id"] = f"G{i}"
            g.pop("_text", None)
        return {"topic": topic, "note": "Candidate gaps are hypotheses derived from the ingested papers only; verify against the wider literature.",
                "gaps": gaps[:max_gaps]}

    def _topic_relevance(self, topic: str):
        embedder = get_embedder()
        tvec = embedder.encode([topic])[0]

        def score(text: str) -> float:
            v = embedder.encode([text])[0]
            return max(0.0, float(v @ tvec))
        return score

    # ------------------------------------------------------------------ escape hatch
    def graph_query(self, cypher: str) -> dict:
        """Read-only Cypher for custom multi-hop questions. Writes are rejected by FalkorDB's read-only mode."""
        if re.search(r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP|CALL\s+db\.idx\.\w+\.create)\b", cypher, re.I):
            return {"error": "Only read-only queries are allowed."}
        if not re.search(r"\bLIMIT\s+\d+", cypher, re.I):
            cypher = cypher.rstrip().rstrip(";") + " LIMIT 50"
        try:
            rows = self.store.query(cypher, read_only=True)
        except Exception as e:
            return {"error": f"Query failed: {e}"}
        clean = []
        for row in rows[:50]:
            clean.append({k: _plain(v) for k, v in row.items()})
        return {"rows": clean}


def _plain(value):
    """Convert FalkorDB Node/Edge objects into JSON-friendly dicts without embeddings."""
    props = getattr(value, "properties", None)
    if isinstance(props, dict):
        d = {k: v for k, v in props.items() if k != "embedding"}
        labels = getattr(value, "labels", None) or ([getattr(value, "relation", None)] if getattr(value, "relation", None) else None)
        if labels:
            d["_labels"] = labels
        if "text" in d:
            d["text"] = _trim(d["text"])
        return d
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


# JSON schemas shared by the agent (Claude tool definitions) and documentation.
TOOL_SPECS: list[dict] = [
    {"name": "list_papers", "description": "List all papers in the knowledge graph with ids, titles, authors and years. Call this first to see the corpus.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "search_evidence", "description": "Hybrid semantic + keyword search over page-level evidence passages from all papers. Returns chunk_ids to cite, page numbers, and statements extracted from each passage.",
     "input_schema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "Natural-language search query."},
         "top_k": {"type": "integer", "description": "Number of passages (1-15, default 6)."},
         "paper_id": {"type": "string", "description": "Optional: restrict to one paper."}},
         "required": ["query"], "additionalProperties": False}},
    {"name": "get_paper", "description": "Full structured record of one paper: metadata, methods, datasets, claims, findings and limitations, each with evidence chunk_id and page.",
     "input_schema": {"type": "object", "properties": {"paper_id": {"type": "string"}}, "required": ["paper_id"], "additionalProperties": False}},
    {"name": "explore_entity", "description": "Multi-hop traversal from a method or dataset: which papers use it, what they found about it, what else they used, and the limitations of those papers.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string", "description": "Method or dataset name, e.g. 'Graph Attention Network' or 'KIBA'."},
         "entity_type": {"type": "string", "enum": ["auto", "method", "dataset"]}},
         "required": ["name"], "additionalProperties": False}},
    {"name": "find_related_papers", "description": "Papers connected to a paper through shared methods/datasets, similar claims, contradictions, or limitations another paper addresses.",
     "input_schema": {"type": "object", "properties": {"paper_id": {"type": "string"}}, "required": ["paper_id"], "additionalProperties": False}},
    {"name": "compare_claims", "description": "Gather claims and findings about a topic across papers, grouped by paper, with detected contradictions (CONTRADICTS) and closely related statements (SIMILAR_TO; judge yourself whether they agree).",
     "input_schema": {"type": "object", "properties": {
         "topic": {"type": "string"}, "top_k": {"type": "integer", "description": "Max statements (2-20, default 10)."}},
         "required": ["topic"], "additionalProperties": False}},
    {"name": "find_research_gaps", "description": "Candidate research gaps derived from the graph: unaddressed or recurring limitations, open future work, conflicting evidence, and untested method-dataset combinations. Each gap includes evidence.",
     "input_schema": {"type": "object", "properties": {
         "topic": {"type": "string", "description": "Optional topic to rank gaps by relevance."},
         "max_gaps": {"type": "integer", "description": "Default 8."}},
         "additionalProperties": False}},
    {"name": "get_evidence", "description": "Fetch the full text, paper and page of specific evidence chunks to verify a citation.",
     "input_schema": {"type": "object", "properties": {"chunk_ids": {"type": "array", "items": {"type": "string"}}},
                      "required": ["chunk_ids"], "additionalProperties": False}},
    {"name": "graph_query", "description": "Run a read-only Cypher query on the FalkorDB graph for multi-hop questions the other tools don't cover. Labels: Paper, Author, Chunk, Method, Dataset, Claim, Finding, Limitation. Relationships: AUTHORED, HAS_CHUNK, USES_METHOD, USES_DATASET, MAKES_CLAIM, REPORTS_FINDING, HAS_LIMITATION, SUPPORTED_BY, ABOUT_METHOD, EVALUATED_ON, SIMILAR_TO, CONTRADICTS, ADDRESSED_BY. Return properties (e.g. p.title), not whole nodes.",
     "input_schema": {"type": "object", "properties": {"cypher": {"type": "string"}}, "required": ["cypher"], "additionalProperties": False}},
]


def call_tool(tools: ResearchTools, name: str, args: dict) -> dict:
    fn = getattr(tools, name, None)
    if name not in {s["name"] for s in TOOL_SPECS} or fn is None:
        return {"error": f"Unknown tool {name}"}
    return fn(**args)
