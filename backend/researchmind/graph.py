"""FalkorDB knowledge-graph store.

Schema
  (:Paper {id, title, authors, year, abstract, source_file, num_pages, sha256, extractor})
  (:Author {id, name})-[:AUTHORED]->(:Paper)
  (:Paper)-[:HAS_CHUNK]->(:Chunk {id, paper_id, page, section, text, embedding})
  (:Paper)-[:USES_METHOD {chunk_id, quote}]->(:Method {id, name})          shared across papers
  (:Paper)-[:USES_DATASET {chunk_id, quote}]->(:Dataset {id, name})        shared across papers
  (:Paper)-[:MAKES_CLAIM]->(:Claim)  (:Paper)-[:REPORTS_FINDING]->(:Finding)
  (:Paper)-[:HAS_LIMITATION]->(:Limitation {kind})
  (:Claim|Finding|Limitation)-[:SUPPORTED_BY {quote}]->(:Chunk)            evidence
  (:Claim|Finding)-[:ABOUT_METHOD]->(:Method)  (:Finding)-[:EVALUATED_ON]->(:Dataset)
  Cross-paper edges (computed with embeddings):
  (:Claim|Finding)-[:SIMILAR_TO {score}]->(:Claim|Finding)
  (:Claim|Finding)-[:CONTRADICTS {score}]->(:Claim|Finding)
  (:Limitation)-[:SIMILAR_TO {score}]->(:Limitation)                      recurring limitation
  (:Limitation)-[:ADDRESSED_BY {score}]->(:Claim|Finding)                  another paper tackles it

All writes use MERGE on deterministic ids, so re-ingesting a paper never duplicates nodes.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone

from falkordb import FalkorDB
from redis.exceptions import AuthenticationError, ConnectionError, ResponseError, TimeoutError

from .config import get_settings
from .embeddings import DIM, get_embedder
from .extract import Extraction, slug
from .ingest import ParsedPaper

log = logging.getLogger(__name__)

STATEMENT_LABELS = ("Claim", "Finding", "Limitation")
SIMILAR_THRESHOLD = 0.62
CONTRADICT_THRESHOLD = 0.5
ADDRESS_THRESHOLD = 0.5

NEG = re.compile(r"\b(not|no|fail|fails|failed|worse|underperform\w*|drop|drops|decrease\w*|cannot|unable|poor\w*|degrad\w*)\b", re.I)
POS = re.compile(r"\b(improv\w*|outperform\w*|generaliz\w* well|better|increase\w*|gain\w*|effective|succeed\w*|achiev\w*)\b", re.I)


class GraphConnectionError(Exception):
    """Raised with a user-friendly message when FalkorDB cannot be reached."""


def polarity(text: str) -> int:
    """Rough sentiment of a scientific statement: +1 positive result, -1 negative, 0 neutral."""
    neg, pos = len(NEG.findall(text)), len(POS.findall(text))
    return 0 if neg == pos else (1 if pos > neg else -1)


def statement_id(paper_id: str, label: str, text: str) -> str:
    return f"{paper_id}:{label[:3].lower()}:{hashlib.sha1(text.strip().lower().encode()).hexdigest()[:10]}"


class GraphStore:
    def __init__(self, url: str | None = None, graph_name: str | None = None):
        settings = get_settings()
        url = url or settings.falkordb_url
        if not url:
            raise GraphConnectionError("FALKORDB_URL is not set. Copy .env.example to .env and add your FalkorDB Cloud URL.")
        try:
            self.db = FalkorDB.from_url(url)
            self.graph = self.db.select_graph(graph_name or settings.graph_name)
            self.graph.query("RETURN 1")
        except AuthenticationError as e:
            raise GraphConnectionError("FalkorDB authentication failed - check the password in FALKORDB_URL.") from e
        except (ConnectionError, TimeoutError, OSError) as e:
            raise GraphConnectionError(f"Could not reach FalkorDB ({e}). Check FALKORDB_URL host/port and that the instance is running.") from e
        self.graph_name = graph_name or settings.graph_name
        self._embedder_checked = False
        self.ensure_indexes()  # also materializes the graph key so read-only queries work on a fresh graph

    # ------------------------------------------------------------------ basics
    def close(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def query(self, cypher: str, params: dict | None = None, read_only: bool = False) -> list[dict]:
        """Run Cypher and return rows as dicts keyed by the RETURN aliases."""
        fn = self.graph.ro_query if read_only else self.graph.query
        result = fn(cypher, params or {})
        columns = [h[1] if isinstance(h, (list, tuple)) else h for h in (result.header or [])]
        columns = [c.decode() if isinstance(c, bytes) else c for c in columns]
        return [dict(zip(columns, row)) for row in result.result_set]

    def ensure_indexes(self) -> None:
        def ignore_existing(fn, *args, **kwargs):
            try:
                fn(*args, **kwargs)
            except ResponseError as e:
                if "already indexed" not in str(e).lower():
                    raise
        for label in ("Paper", "Author", "Chunk", "Method", "Dataset", "Meta", *STATEMENT_LABELS):
            ignore_existing(self.graph.create_node_range_index, label, "id")
        ignore_existing(self.graph.create_node_range_index, "Chunk", "paper_id")
        ignore_existing(self.graph.create_node_fulltext_index, "Chunk", "text")
        for label in ("Chunk", *STATEMENT_LABELS):
            ignore_existing(self.graph.create_node_vector_index, label, "embedding", dim=DIM, similarity_function="cosine")

    def check_embedder(self) -> None:
        if self._embedder_checked:
            return
        embedder = get_embedder()
        rows = self.query("MERGE (m:Meta {id: 'embedding'}) ON CREATE SET m.model = $model RETURN m.model AS model",
                          {"model": embedder.name})
        if rows and rows[0]["model"] != embedder.name:
            log.warning("Graph embeddings were built with %s but current embedder is %s. "
                        "Re-ingest papers (or reset the graph) for consistent semantic search.", rows[0]["model"], embedder.name)
        self._embedder_checked = True

    # ------------------------------------------------------------------ writes
    def get_paper(self, paper_id: str) -> dict | None:
        rows = self.query("MATCH (p:Paper {id: $id}) RETURN p.id AS id, p.sha256 AS sha256, p.extractor AS extractor, "
                          "p.title AS title, coalesce(p.status, 'processed') AS status",
                          {"id": paper_id}, read_only=True)
        return rows[0] if rows else None

    def delete_paper(self, paper_id: str) -> None:
        """Remove a paper and everything it owns; shared Method/Dataset/Author nodes are kept if still used."""
        self.query("MATCH (p:Paper {id: $id})-[:HAS_CHUNK|MAKES_CLAIM|REPORTS_FINDING|HAS_LIMITATION]->(n) DETACH DELETE n", {"id": paper_id})
        self.query("MATCH (p:Paper {id: $id}) DETACH DELETE p", {"id": paper_id})
        self.query("MATCH (n) WHERE (n:Method OR n:Dataset OR n:Author) AND NOT (n)--() DELETE n")

    def record_failure(self, paper_id: str, sha256: str, filename: str, code: str, message: str,
                       file_size: int | None = None) -> None:
        """Remember a failed ingestion (keyed by content hash) so the UI can report it and retries are idempotent."""
        self.query(
            """MERGE (p:Paper {id: $id})
               SET p.sha256 = $sha256, p.source_file = $filename, p.status = 'failed', p.error_code = $code,
                   p.error = $message, p.file_size = $size, p.updated_at = $now""",
            {"id": paper_id, "sha256": sha256, "filename": filename, "code": code, "message": message,
             "size": file_size, "now": datetime.now(timezone.utc).isoformat(timespec="seconds")})

    def upsert_paper(self, paper: ParsedPaper, extraction: Extraction, document_key: str | None = None,
                     file_size: int | None = None) -> dict:
        """Write a parsed paper + extracted knowledge. Replaces any previous version of the same paper."""
        self.check_embedder()
        embedder = get_embedder()

        # Same paper re-exported with different bytes (e.g. a new arXiv version): match on the
        # detected title and replace. Papers without a detected title are never merged this way.
        if paper.title_detected:
            norm_title = re.sub(r"[^a-z0-9]", "", paper.title.lower())
            for row in self.query("""MATCH (p:Paper) WHERE coalesce(p.status, 'processed') = 'processed'
                                     AND coalesce(p.title_detected, true) = true
                                     RETURN p.id AS id, p.title AS title""", read_only=True):
                if row["id"] != paper.id and re.sub(r"[^a-z0-9]", "", (row["title"] or "").lower()) == norm_title:
                    log.info("Replacing earlier version of '%s' (%s)", paper.title, row["id"])
                    self.delete_paper(row["id"])
        self.delete_paper(paper.id)

        self.query(
            """MERGE (p:Paper {id: $id})
               SET p.title = $title, p.authors = $authors, p.year = $year, p.abstract = $abstract,
                   p.source_file = $source_file, p.num_pages = $num_pages, p.sha256 = $sha256,
                   p.extractor = $extractor, p.ingested_at = $now, p.updated_at = $now,
                   p.status = 'processed', p.title_detected = $title_detected, p.document_key = $document_key,
                   p.file_size = $file_size, p.error = null, p.error_code = null""",
            {"id": paper.id, "title": paper.title, "authors": paper.authors, "year": paper.year,
             "abstract": paper.abstract, "source_file": paper.source_file, "num_pages": paper.num_pages,
             "sha256": paper.sha256, "extractor": extraction.extractor, "title_detected": paper.title_detected,
             "document_key": document_key, "file_size": file_size,
             "now": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        )
        if paper.authors:
            self.query(
                """MATCH (p:Paper {id: $pid}) UNWIND $authors AS a
                   MERGE (au:Author {id: a.id}) SET au.name = a.name MERGE (au)-[:AUTHORED]->(p)""",
                {"pid": paper.id, "authors": [{"id": slug(a), "name": a} for a in paper.authors]},
            )

        # Chunks (evidence passages) with embeddings
        chunk_vecs = embedder.encode([c.text for c in paper.chunks])
        self.query(
            """MATCH (p:Paper {id: $pid}) UNWIND $rows AS r
               MERGE (c:Chunk {id: r.id})
               SET c.paper_id = $pid, c.page = r.page, c.section = r.section, c.text = r.text, c.embedding = vecf32(r.vec)
               MERGE (p)-[:HAS_CHUNK]->(c)""",
            {"pid": paper.id, "rows": [{"id": c.id, "page": c.page, "section": c.section, "text": c.text, "vec": v.tolist()}
                                       for c, v in zip(paper.chunks, chunk_vecs)]},
        )

        # Shared entities
        for rel, label, items in (("USES_METHOD", "Method", extraction.methods), ("USES_DATASET", "Dataset", extraction.datasets)):
            rows = [{"id": slug(i.text), "name": i.text, "chunk_id": i.chunk_id, "quote": i.quote} for i in items if slug(i.text)]
            if rows:
                self.query(
                    f"""MATCH (p:Paper {{id: $pid}}) UNWIND $rows AS r
                        MERGE (e:{label} {{id: r.id}}) ON CREATE SET e.name = r.name
                        MERGE (p)-[x:{rel}]->(e) SET x.chunk_id = r.chunk_id, x.quote = r.quote""",
                    {"pid": paper.id, "rows": rows},
                )

        # Statements with evidence links
        method_names = {slug(m.text): m.text for m in extraction.methods}
        dataset_names = {slug(d.text): d.text for d in extraction.datasets}
        new_statements: list[dict] = []
        for label, rel, items in (("Claim", "MAKES_CLAIM", extraction.claims),
                                  ("Finding", "REPORTS_FINDING", extraction.findings),
                                  ("Limitation", "HAS_LIMITATION", extraction.limitations)):
            if not items:
                continue
            vecs = embedder.encode([i.text for i in items])
            rows = []
            for item, vec in zip(items, vecs):
                low = item.text.lower() + " " + item.quote.lower()
                rows.append({
                    "id": statement_id(paper.id, label, item.text), "text": item.text, "quote": item.quote,
                    "chunk_id": item.chunk_id, "kind": item.kind or label.lower(), "polarity": polarity(item.text),
                    "vec": vec.tolist(),
                    "methods": [k for k, n in method_names.items() if n.lower() in low],
                    "datasets": [k for k, n in dataset_names.items() if n.lower() in low],
                })
            self.query(
                f"""MATCH (p:Paper {{id: $pid}}) UNWIND $rows AS r
                    MERGE (s:{label} {{id: r.id}})
                    SET s.paper_id = $pid, s.text = r.text, s.kind = r.kind, s.polarity = r.polarity, s.embedding = vecf32(r.vec)
                    MERGE (p)-[:{rel}]->(s)
                    WITH s, r MATCH (c:Chunk {{id: r.chunk_id}}) MERGE (s)-[e:SUPPORTED_BY]->(c) SET e.quote = r.quote""",
                {"pid": paper.id, "rows": rows},
            )
            if label != "Limitation":
                self.query(
                    f"""UNWIND $rows AS r MATCH (s:{label} {{id: r.id}})
                        UNWIND r.methods AS mid MATCH (m:Method {{id: mid}}) MERGE (s)-[:ABOUT_METHOD]->(m)""",
                    {"rows": rows})
                self.query(
                    f"""UNWIND $rows AS r MATCH (s:{label} {{id: r.id}})
                        UNWIND r.datasets AS did MATCH (d:Dataset {{id: did}}) MERGE (s)-[:EVALUATED_ON]->(d)""",
                    {"rows": rows})
            new_statements += [{**r, "label": label} for r in rows]

        links = self._link_across_papers(paper.id, new_statements)
        return {"paper_id": paper.id, "chunks": len(paper.chunks), **extraction.counts(), "cross_paper_links": links}

    def _nearest(self, label: str, vec: list[float], k: int = 8) -> list[dict]:
        return self.query(
            f"""CALL db.idx.vector.queryNodes('{label}', 'embedding', $k, vecf32($vec)) YIELD node, score
                RETURN node.id AS id, node.paper_id AS paper_id, node.text AS text, node.polarity AS polarity, 1 - score AS sim""",
            {"k": k, "vec": vec}, read_only=True)

    def _link_across_papers(self, paper_id: str, statements: list[dict]) -> int:
        """Create SIMILAR_TO / CONTRADICTS / ADDRESSED_BY edges between this paper's statements and other papers'."""
        edges: list[tuple[str, str, str, float]] = []
        for s in statements:
            targets = ("Claim", "Finding") if s["label"] != "Limitation" else ("Limitation", "Claim", "Finding")
            for target in targets:
                for hit in self._nearest(target, s["vec"]):
                    if hit["paper_id"] == paper_id:
                        continue
                    sim = float(hit["sim"])
                    if s["label"] == "Limitation":
                        if target == "Limitation" and sim >= SIMILAR_THRESHOLD:
                            edges.append(("SIMILAR_TO", s["id"], hit["id"], sim))
                        elif target != "Limitation" and sim >= ADDRESS_THRESHOLD:
                            edges.append(("ADDRESSED_BY", s["id"], hit["id"], sim))
                    else:
                        if sim >= CONTRADICT_THRESHOLD and s["polarity"] * (hit["polarity"] or 0) < 0:
                            edges.append(("CONTRADICTS", s["id"], hit["id"], sim))
                        elif sim >= SIMILAR_THRESHOLD:
                            edges.append(("SIMILAR_TO", s["id"], hit["id"], sim))
            # Older limitations that this new paper's claims/findings may address
            if s["label"] != "Limitation":
                for hit in self._nearest("Limitation", s["vec"]):
                    if hit["paper_id"] != paper_id and float(hit["sim"]) >= ADDRESS_THRESHOLD:
                        edges.append(("ADDRESSED_BY", hit["id"], s["id"], float(hit["sim"])))
        for rel in ("SIMILAR_TO", "CONTRADICTS", "ADDRESSED_BY"):
            rows = [{"a": a, "b": b, "score": round(sc, 3)} for r, a, b, sc in edges if r == rel]
            if rows:
                self.query(
                    f"""UNWIND $rows AS r MATCH (a {{id: r.a}}), (b {{id: r.b}})
                        MERGE (a)-[x:{rel}]->(b) SET x.score = r.score""", {"rows": rows})
        return len(edges)

    # ------------------------------------------------------------------ reads
    def stats(self) -> dict:
        rows = self.query(
            """MATCH (n) WHERE n:Paper OR n:Chunk OR n:Method OR n:Dataset OR n:Claim OR n:Finding OR n:Limitation OR n:Author
               RETURN labels(n)[0] AS label, count(n) AS total""", read_only=True)
        out = {r["label"]: r["total"] for r in rows}
        rel = self.query("MATCH ()-[r]->() RETURN count(r) AS n", read_only=True)
        out["relationships"] = rel[0]["n"] if rel else 0
        return out

    def list_papers(self) -> list[dict]:
        return self.query(
            """MATCH (p:Paper) WHERE p.sha256 IS NOT NULL AND coalesce(p.status, 'processed') = 'processed'
               OPTIONAL MATCH (p)-[:HAS_CHUNK]->(c)
               RETURN p.id AS id, p.title AS title, p.authors AS authors, p.year AS year,
                      p.source_file AS source_file, p.extractor AS extractor, count(c) AS chunks
               ORDER BY p.year DESC, p.title""", read_only=True)

    def reset(self) -> None:
        """Delete the whole graph (used by tests and the UI's reset button)."""
        try:
            self.graph.delete()
        except ResponseError:
            pass
        self._embedder_checked = False
        self.ensure_indexes()
