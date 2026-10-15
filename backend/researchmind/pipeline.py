"""End-to-end ingestion: PDF -> parsed paper -> page store + extracted knowledge -> FalkorDB."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .config import get_settings
from .documents import DocumentStore
from .extract import HeuristicExtractor, get_extractor
from .graph import GraphStore
from .ingest import IngestionError, file_sha256, parse_pdf
from .llm import get_extraction_llm

log = logging.getLogger(__name__)


def ingest_file(path: str | Path, store: GraphStore, force: bool = False, use_llm: bool | None = None,
                progress=lambda msg: None, source_name: str | None = None,
                documents: DocumentStore | None = None, processed_dir: Path | None = None) -> dict:
    """Ingest one PDF and return a summary dict with status "ingested" or "unchanged".

    Unchanged papers (same content hash, same extractor, page store present) are skipped without
    re-parsing unless force=True. Unreadable PDFs are recorded as failed Paper nodes and the
    IngestionError is re-raised for the caller to report.
    """
    settings = get_settings()
    path = Path(path)
    source_name = source_name or path.name
    documents = documents or DocumentStore()

    sha = file_sha256(path)
    paper_id = "p_" + sha[:12]
    file_size = path.stat().st_size

    llm = get_extraction_llm() if (settings.use_llm_extraction if use_llm is None else use_llm) else None
    extractor = get_extractor(llm)

    existing = store.get_paper(paper_id)
    if (existing and not force and existing["status"] == "processed" and existing.get("extractor") == extractor.name
            and documents.exists(paper_id)):
        progress(f"Already ingested: {existing['title']}")
        return {"paper_id": paper_id, "title": existing["title"], "status": "unchanged"}

    progress(f"Parsing {source_name}")
    try:
        paper = parse_pdf(path)
    except IngestionError as e:
        message = str(e).replace(path.name, source_name)  # report the user's file name, not the stored one
        store.record_failure(paper_id, sha, source_name, e.code, message, file_size)
        raise IngestionError(message, e.code) from e
    paper.source_file = source_name

    progress(f"Extracting knowledge with {extractor.name} extractor")
    try:
        extraction = extractor.extract(paper)
    except Exception as e:
        if extractor.name == "heuristic":
            raise
        log.warning("LLM extraction failed (%s); falling back to heuristic extractor.", e)
        progress(f"LLM extraction failed ({type(e).__name__}); using heuristic extractor")
        extraction = HeuristicExtractor().extract(paper)

    progress("Storing page text")
    document_key = documents.save(paper.id, paper.pages, {
        "paper_id": paper.id, "source_file": source_name, "sha256": paper.sha256, "pdf_metadata": paper.pdf_metadata})

    progress("Writing to knowledge graph")
    summary = store.upsert_paper(paper, extraction, document_key=document_key, file_size=file_size)

    # Keep a JSON copy of what was extracted, for inspection and debugging.
    out_dir = processed_dir or settings.data_dir / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    paper_meta = {k: v for k, v in paper.to_dict().items() if k != "pages"}
    (out_dir / f"{paper.id}.json").write_text(
        json.dumps({"paper": paper_meta, "extraction": extraction.to_dict()}, indent=2), encoding="utf-8")

    progress(f"Ingested: {paper.title}")
    return {"title": paper.title, "status": "ingested", "extractor": extraction.extractor,
            "page_count": paper.num_pages, "title_detected": paper.title_detected, **summary}


def ingest_directory(directory: str | Path, store: GraphStore, force: bool = False, progress=lambda msg: None) -> list[dict]:
    results = []
    for pdf in sorted(Path(directory).glob("*.pdf")):
        try:
            results.append(ingest_file(pdf, store, force=force, progress=progress))
        except Exception as e:  # one bad PDF should not stop the batch
            log.exception("Failed to ingest %s", pdf)
            results.append({"file": pdf.name, "status": "error", "error": str(e)})
    return results
