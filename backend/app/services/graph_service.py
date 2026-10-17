"""Read models for the API, built from parameterized Cypher over FalkorDB."""

from __future__ import annotations

from researchmind.documents import DocumentStore
from researchmind.graph import GraphStore

PAPER_FIELDS = """p.id AS id, p.title AS title, coalesce(p.title_detected, true) AS title_detected,
                  p.source_file AS filename, coalesce(p.status, 'processed') AS status, p.num_pages AS page_count,
                  p.authors AS authors, p.year AS year, p.file_size AS file_size, p.error AS error,
                  p.error_code AS error_code, coalesce(p.updated_at, p.ingested_at) AS updated_at"""


def _summary(row: dict) -> dict:
    title = row.get("title") if row.get("title_detected") and row.get("status") == "processed" else None
    return {**row, "title": title, "display_title": title or row.get("filename") or row["id"],
            "authors": row.get("authors") or []}


def paper_counts(store: GraphStore) -> dict:
    rows = store.query(
        """MATCH (p:Paper) WHERE p.sha256 IS NOT NULL
           RETURN coalesce(p.status, 'processed') AS status, count(p) AS n""", read_only=True)
    counts = {r["status"]: r["n"] for r in rows}
    processed, failed = counts.get("processed", 0), counts.get("failed", 0)
    return {"total": processed + failed, "processed": processed, "failed": failed}


def list_papers(store: GraphStore, status: str | None = None, search: str | None = None,
                limit: int = 50, offset: int = 0) -> dict:
    where = ["p.sha256 IS NOT NULL"]
    params: dict = {"limit": limit, "offset": offset}
    if status:
        where.append("coalesce(p.status, 'processed') = $status")
        params["status"] = status
    if search:
        where.append("(toLower(coalesce(p.title, '')) CONTAINS $q OR toLower(coalesce(p.source_file, '')) CONTAINS $q)")
        params["q"] = search.lower()
    clause = " AND ".join(where)
    total = store.query(f"MATCH (p:Paper) WHERE {clause} RETURN count(p) AS n", params, read_only=True)[0]["n"]
    rows = store.query(
        f"""MATCH (p:Paper) WHERE {clause}
            RETURN {PAPER_FIELDS}
            ORDER BY coalesce(p.updated_at, p.ingested_at) DESC, p.id SKIP $offset LIMIT $limit""",
        params, read_only=True)
    return {"papers": [_summary(r) for r in rows], "counts": paper_counts(store),
            "total_matching": total, "limit": limit, "offset": offset}


def get_paper_detail(store: GraphStore, documents: DocumentStore, paper_id: str,
                     page: int = 1, page_size: int = 3) -> dict | None:
    rows = store.query(
        f"""MATCH (p:Paper {{id: $id}})
            RETURN {PAPER_FIELDS}, p.sha256 AS sha256, p.abstract AS abstract,
                   p.ingested_at AS ingested_at, p.extractor AS extractor""",
        {"id": paper_id}, read_only=True)
    if not rows:
        return None
    row = rows[0]
    paper = _summary(row)
    paper["title_detected"] = row["title_detected"] if row["status"] == "processed" else None

    meta = documents.meta(paper_id) if documents.exists(paper_id) else None
    paper["pdf_metadata"] = (meta or {}).get("pdf_metadata", {})
    if row["status"] == "processed":
        paper["knowledge"] = _knowledge(store, paper_id, row.get("extractor"))

    total_pages = (meta or {}).get("page_count") or row.get("page_count") or 0
    page = max(1, min(page, max(total_pages, 1)))
    pages = documents.pages(paper_id, start=(page - 1) * page_size + 1, count=page_size) if meta else []
    return {"paper": paper, "pages": pages, "text_available": bool(meta),
            "pagination": {"page": page, "page_size": page_size,
                           "total_pages": -(-total_pages // page_size) if total_pages else 0}}


def _knowledge(store: GraphStore, paper_id: str, extractor: str | None) -> dict:
    def entities(rel: str) -> list[dict]:
        return store.query(
            f"""MATCH (p:Paper {{id: $id}})-[r:{rel}]->(e) OPTIONAL MATCH (c:Chunk {{id: r.chunk_id}})
                RETURN e.name AS name, c.page AS page ORDER BY e.name""", {"id": paper_id}, read_only=True)

    counts = store.query(
        """MATCH (p:Paper {id: $id})
           OPTIONAL MATCH (p)-[:MAKES_CLAIM]->(c) WITH p, count(c) AS claims
           OPTIONAL MATCH (p)-[:REPORTS_FINDING]->(f) WITH p, claims, count(f) AS findings
           OPTIONAL MATCH (p)-[:HAS_LIMITATION]->(l) WITH p, claims, findings, count(l) AS limitations
           OPTIONAL MATCH (p)-[:HAS_CHUNK]->(ch)
           RETURN claims, findings, limitations, count(ch) AS chunks, collect(DISTINCT ch.section) AS sections""",
        {"id": paper_id}, read_only=True)[0]
    return {"extractor": extractor, "methods": entities("USES_METHOD"), "datasets": entities("USES_DATASET"), **counts}


def graph_stats(store: GraphStore) -> dict:
    stats = store.stats()
    rels = stats.pop("relationships", 0)
    return {"nodes": stats, "relationships": rels}


def graph_overview(store: GraphStore, limit: int = 60) -> dict:
    """Papers with their own methods/datasets, for the React Flow view. Papers are never linked to each other."""
    rows = store.query(
        """MATCH (p:Paper) WHERE coalesce(p.status, 'processed') = 'processed' AND p.sha256 IS NOT NULL
           WITH p ORDER BY p.ingested_at DESC LIMIT $limit
           OPTIONAL MATCH (p)-[r:USES_METHOD|USES_DATASET]->(e)
           RETURN p.id AS pid, p.title AS title, p.source_file AS filename,
                  type(r) AS rel, e.id AS eid, e.name AS ename""", {"limit": limit}, read_only=True)
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    for r in rows:
        nodes.setdefault(r["pid"], {"id": r["pid"], "type": "paper", "label": r["title"] or r["filename"] or r["pid"]})
        if r["eid"]:
            kind = "method" if r["rel"] == "USES_METHOD" else "dataset"
            nid = f"{kind}:{r['eid']}"
            nodes.setdefault(nid, {"id": nid, "type": kind, "label": r["ename"]})
            edges.append({"id": f"{r['pid']}->{nid}", "source": r["pid"], "target": nid, "type": r["rel"]})
    return {"nodes": list(nodes.values()), "edges": edges}


def delete_paper(store: GraphStore, documents: DocumentStore, paper_id: str, upload_dir) -> bool:
    if not store.query("MATCH (p:Paper {id: $id}) RETURN p.id AS id", {"id": paper_id}, read_only=True):
        return False
    store.delete_paper(paper_id)
    documents.delete(paper_id)
    (upload_dir / f"{paper_id}.pdf").unlink(missing_ok=True)
    return True
