"""Paper upload, listing, detail and deletion."""

import asyncio
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from researchmind.accounts import User
from researchmind.documents import DocumentStore
from researchmind.graph import GraphStore
from researchmind.projects import Project

from ..auth import get_current_user
from ..config import get_api_settings
from ..database import get_project, get_store
from ..ratelimit import get_limiters
from ..schemas.paper import PaperDetailResponse, PaperListResponse, UploadResponse
from ..services import graph_service
from ..services.pdf_service import StagedUpload, UploadRejected, process_upload, stage_upload

log = logging.getLogger("researchmind.api.papers")
router = APIRouter(prefix="/papers", tags=["papers"])

# Proxies drop a request that sends nothing for a while (Vercel: 120 s), and a batch of large PDFs can
# take longer to parse and extract. A batch still running after this long is answered as a stream that
# sends a space every KEEPALIVE_SECONDS, then the JSON body.
KEEPALIVE_SECONDS = 15

PaperId = Annotated[str, Path(pattern=r"^p_[0-9a-f]{12}$", description="Paper id: p_ + first 12 hex chars of the SHA-256")]


def get_documents(project: Project = Depends(get_project)) -> DocumentStore:
    return DocumentStore(project.documents_dir)


@router.post("/upload", response_model=UploadResponse)
async def upload_papers(files: Annotated[list[UploadFile], File(description="One or more PDF files")],
                        store: GraphStore = Depends(get_store), project: Project = Depends(get_project),
                        user: User = Depends(get_current_user)) -> dict | StreamingResponse:
    settings = get_api_settings()
    if len(files) > settings.max_files_per_upload:
        raise HTTPException(400, f"Too many files: at most {settings.max_files_per_upload} per upload.")
    get_limiters().uploads.hit(user.id, cost=len(files))

    # Stage every file while the request's uploads are still open; processing may outlive the handler.
    staged: list[StagedUpload | dict] = []
    for f in files:
        try:
            staged.append(await stage_upload(f, project.upload_dir))
        except UploadRejected as e:
            staged.append({"filename": f.filename or "unnamed", "status": "rejected",
                           "message": str(e), "error_code": e.code})

    async def process() -> dict:
        results = []
        for item in staged:
            # Parsing and graph writes are blocking work: keep them off the event loop.
            results.append(item if isinstance(item, dict) else await run_in_threadpool(process_upload, item, store, project))
        summary = {"received": len(files), **{k: sum(r["status"] == k for r in results)
                                              for k in ("processed", "duplicate", "failed", "rejected")}}
        log.info("Upload batch: %s", summary)
        return {"results": results, "summary": summary}

    task = asyncio.ensure_future(process())
    done, _ = await asyncio.wait({task}, timeout=KEEPALIVE_SECONDS)
    if done:
        return task.result()
    return StreamingResponse(_keep_alive(task), media_type="application/json")


async def _keep_alive(task: asyncio.Future):
    """A space every KEEPALIVE_SECONDS until the batch is done (JSON allows leading whitespace), then the body."""
    while not task.done():
        done, _ = await asyncio.wait({task}, timeout=KEEPALIVE_SECONDS)
        if not done:
            yield b" "
    yield UploadResponse.model_validate(task.result()).model_dump_json().encode()


@router.get("", response_model=PaperListResponse)
def list_papers(status: Literal["processed", "failed"] | None = None,
                search: Annotated[str | None, Query(max_length=200)] = None,
                limit: Annotated[int, Query(ge=1, le=200)] = 50,
                offset: Annotated[int, Query(ge=0)] = 0,
                store: GraphStore = Depends(get_store)) -> dict:
    return graph_service.list_papers(store, status=status, search=search, limit=limit, offset=offset)


@router.get("/{paper_id}", response_model=PaperDetailResponse)
def get_paper(paper_id: PaperId,
              page: Annotated[int, Query(ge=1)] = 1,
              page_size: Annotated[int, Query(ge=1, le=20)] = 3,
              store: GraphStore = Depends(get_store),
              documents: DocumentStore = Depends(get_documents)) -> dict:
    detail = graph_service.get_paper_detail(store, documents, paper_id, page=page, page_size=page_size)
    if detail is None:
        raise HTTPException(404, "Paper not found.")
    return detail


@router.get("/{paper_id}/file", response_class=FileResponse)
def download_pdf(paper_id: PaperId, store: GraphStore = Depends(get_store), project: Project = Depends(get_project)):
    rows = store.query("MATCH (p:Paper {id: $id}) RETURN p.source_file AS filename", {"id": paper_id}, read_only=True)
    path = project.upload_dir / f"{paper_id}.pdf"
    if not rows or not path.exists():
        raise HTTPException(404, "Original PDF not available.")
    return FileResponse(path, media_type="application/pdf", filename=rows[0]["filename"] or f"{paper_id}.pdf",
                        content_disposition_type="inline")


@router.delete("/{paper_id}", status_code=204)
def delete_paper(paper_id: PaperId, store: GraphStore = Depends(get_store), project: Project = Depends(get_project),
                 documents: DocumentStore = Depends(get_documents)) -> None:
    if not graph_service.delete_paper(store, documents, paper_id, project.upload_dir):
        raise HTTPException(404, "Paper not found.")
