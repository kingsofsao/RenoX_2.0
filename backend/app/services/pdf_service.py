"""Upload handling: stream to disk with validation, then run the ingestion pipeline.

Uploads are streamed in 1 MB chunks to a temp file while hashing, so a file is never held
in memory and oversized files are cut off as soon as they cross the limit. Accepted files
are stored content-addressed as <project upload_dir>/<paper_id>.pdf - per project, so the same
PDF in two projects is two independent copies and deleting it in one never affects the other.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from researchmind.documents import DocumentStore
from researchmind.graph import GraphStore
from researchmind.ingest import IngestionError
from researchmind.pipeline import ingest_file
from researchmind.projects import Project

from ..config import get_api_settings

log = logging.getLogger("researchmind.api.pdf")

CHUNK_SIZE = 1024 * 1024
# Serialize ingestion: the embedding model and graph writes are shared, and hackathon-scale
# uploads don't need parallel processing. Also prevents two requests racing on the same file.
_ingest_lock = threading.Lock()


class UploadRejected(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass
class StagedUpload:
    filename: str
    path: Path
    sha256: str
    size: int

    @property
    def paper_id(self) -> str:
        return "p_" + self.sha256[:12]


def safe_filename(name: str | None) -> str:
    base = Path(name or "upload.pdf").name  # strip any client-supplied directories
    base = re.sub(r"[^\w.\- ()\[\]]+", "_", base).strip() or "upload.pdf"
    return base[:180]


async def stage_upload(file: UploadFile, upload_dir: Path | None = None) -> StagedUpload:
    """Validate and stream one upload to disk. Raises UploadRejected for invalid files."""
    settings = get_api_settings()
    upload_dir = upload_dir or settings.upload_dir
    filename = safe_filename(file.filename)
    if not filename.lower().endswith(".pdf"):
        raise UploadRejected(f"{filename} is not a PDF (only .pdf files are accepted).", "not_pdf")

    upload_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(suffix=".pdf.part", dir=upload_dir)
    tmp = Path(tmp_name)
    digest, size, first = hashlib.sha256(), 0, True
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                if first:
                    if not chunk.lstrip().startswith(b"%PDF-"):
                        raise UploadRejected(f"{filename} does not contain PDF data.", "not_pdf")
                    first = False
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise UploadRejected(
                        f"{filename} exceeds the {settings.max_upload_mb} MB upload limit.", "too_large")
                digest.update(chunk)
                out.write(chunk)
        if size == 0:
            raise UploadRejected(f"{filename} is empty.", "empty_file")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    sha = digest.hexdigest()
    final = upload_dir / f"p_{sha[:12]}.pdf"
    if final.exists():
        tmp.unlink(missing_ok=True)  # identical content already stored
    else:
        tmp.replace(final)
    return StagedUpload(filename=filename, path=final, sha256=sha, size=size)


def process_upload(staged: StagedUpload, store: GraphStore, project: Project | None = None) -> dict:
    """Run ingestion for a staged upload into the project's graph and folders."""
    documents = DocumentStore(project.documents_dir) if project else None
    with _ingest_lock:
        try:
            result = ingest_file(staged.path, store, source_name=staged.filename, documents=documents,
                                 processed_dir=project.processed_dir if project else None)
        except IngestionError as e:
            log.info("Ingestion failed for %s (%s): %s", staged.filename, e.code, e)
            return {"filename": staged.filename, "status": "failed", "paper_id": staged.paper_id,
                    "message": str(e), "error_code": e.code}

    if result["status"] == "unchanged":
        return {"filename": staged.filename, "status": "duplicate", "paper_id": result["paper_id"],
                "title": result.get("title"),
                "message": "This file was already ingested (identical content); nothing was duplicated."}
    return {"filename": staged.filename, "status": "processed", "paper_id": result["paper_id"],
            "title": result["title"] if result.get("title_detected") else None,
            "page_count": result.get("page_count"),
            "message": (f"Processed {result.get('page_count')} pages: {result['chunks']} evidence chunks, "
                        f"{result['methods']} methods, {result['datasets']} datasets, {result['claims']} claims, "
                        f"{result['findings']} findings, {result['limitations']} limitations.")}
