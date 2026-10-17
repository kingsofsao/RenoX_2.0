"""Research investigations of one paper, scoped to the signed-in user's project, run by the AI agent over the
paper's knowledge graph and saved to the user's history."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from researchmind.accounts import User
from researchmind.graph import GraphStore
from researchmind.projects import BaseRegistry, Project

from ..auth import get_current_user
from ..config import get_api_settings
from ..database import get_project, get_registry, get_store
from ..ratelimit import get_limiters
from ..schemas.investigation import InvestigationList, InvestigationRequest, InvestigationResponse
from ..services.investigation_service import (AIUnavailable, InvestigationBusy, InvestigationManager, UserBusy, get_manager,
                                              record_to_response)

router = APIRouter(prefix="/investigations", tags=["investigations"])

InvestigationId = Annotated[str, Path(pattern=r"^inv_[0-9a-f]{12}$")]
# Waiting requests get a little headroom past the agent's own time budget (report writing, verification).
WAIT_GRACE_SECONDS = 45


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@router.post("", response_model=InvestigationResponse, responses={202: {"model": InvestigationResponse}})
def create_investigation(body: InvestigationRequest, store: GraphStore = Depends(get_store),
                         project: Project = Depends(get_project), registry: BaseRegistry = Depends(get_registry),
                         manager: InvestigationManager = Depends(get_manager), user: User = Depends(get_current_user)):
    paper = next((p for p in store.list_papers() if p["id"] == body.paper_id), None)
    if paper is None:
        return _error(404, "paper_not_found", "This paper is not in this project, or it has not finished processing.")
    get_limiters().investigations.hit(user.id)
    try:
        job = manager.submit(body.question, store, requirements=body.requirements, project=project, registry=registry,
                             paper_ids=[body.paper_id], paper_title=paper.get("title"),
                             language=body.language or user.language, owner_id=user.id)
    except AIUnavailable as e:
        return _error(503, "ai_unavailable", str(e))
    except UserBusy:
        return _error(429, "busy", "You already have an investigation running. Wait for it to finish, then start the next one.")
    except InvestigationBusy:
        return _error(429, "busy", "The server is busy with other investigations. Please try again in a minute.")

    if not body.wait:
        return JSONResponse(status_code=202, content=InvestigationResponse(**job.to_dict()).model_dump(mode="json"))

    job.done.wait(timeout=get_api_settings().investigation_timeout_s + WAIT_GRACE_SECONDS)
    if job.status == "failed":
        status = 503 if job.error and job.error["code"] in ("database_unavailable", "ai_unavailable") else 500
        return _error(status, job.error["code"], job.error["message"])
    payload = InvestigationResponse(**job.to_dict()).model_dump(mode="json")
    return JSONResponse(status_code=200 if job.status == "completed" else 202, content=payload)


@router.get("", response_model=InvestigationList)
def list_investigations(limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
                        project: Project = Depends(get_project), registry: BaseRegistry = Depends(get_registry),
                        manager: InvestigationManager = Depends(get_manager)) -> dict:
    """Saved investigations of this project, newest first (running ones show their live status)."""
    items, total = registry.list_investigations(project.id, limit, offset)
    for item in items:
        live = manager.get(item["id"], project.id)
        if live is not None:
            item.update(status=live.status, mode=live.mode, provider=live.provider, model=live.model,
                        duration_seconds=live.duration_seconds)
    return {"investigations": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{investigation_id}", response_model=InvestigationResponse)
def get_investigation(investigation_id: InvestigationId, project: Project = Depends(get_project),
                      registry: BaseRegistry = Depends(get_registry),
                      manager: InvestigationManager = Depends(get_manager)) -> dict:
    job = manager.get(investigation_id, project.id)
    if job is not None:
        return job.to_dict()
    rec = registry.get_investigation(project.id, investigation_id)
    if rec is None:
        raise HTTPException(404, "Investigation not found in this project.")
    return record_to_response(rec)


@router.delete("/{investigation_id}", status_code=204)
def delete_investigation(investigation_id: InvestigationId, project: Project = Depends(get_project),
                         registry: BaseRegistry = Depends(get_registry),
                         manager: InvestigationManager = Depends(get_manager)) -> None:
    job = manager.get(investigation_id, project.id)
    if job is not None and job.status in ("queued", "running"):
        raise HTTPException(409, "This investigation is still running; delete it after it finishes.")
    if not registry.delete_investigation(project.id, investigation_id):
        raise HTTPException(404, "Investigation not found in this project.")
