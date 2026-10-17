"""Project workspaces: create, list, read, rename/describe, delete.

Paper, graph and investigation routes are mounted under /api/projects/{project_id}/ (see main.py),
so every operation is resolved to one project's graph on the server.
"""

from fastapi import APIRouter, Depends, HTTPException, Path

from researchmind.projects import BaseRegistry

from ..database import forget_project, get_principal, get_registry, store_for
from ..schemas.project import ProjectCreate, ProjectDelete, ProjectList, ProjectOut, ProjectUpdate
from ..services.investigation_service import InvestigationManager, get_manager

router = APIRouter(prefix="/projects", tags=["projects"])

ProjectIdPath = Path(pattern=r"^prj_[0-9a-f]{10}$")


def _out(project, registry: BaseRegistry, with_counts: bool = True) -> dict:
    data = project.public()
    if with_counts:
        try:
            papers = store_for(project).query(
                "MATCH (p:Paper) WHERE coalesce(p.status, 'processed') = 'processed' RETURN count(p) AS n", read_only=True)[0]["n"]
        except Exception:
            papers = None
        data["paper_count"] = papers
        data["investigation_count"] = registry.list_investigations(project.id, 1, 0)[1]
    return data


@router.get("", response_model=ProjectList)
def list_projects(owner: str = Depends(get_principal), registry: BaseRegistry = Depends(get_registry)) -> dict:
    registry.ensure_workspace(owner)  # every account always has at least one project
    return {"projects": [_out(p, registry) for p in registry.list_projects(owner)]}


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectCreate, owner: str = Depends(get_principal),
                   registry: BaseRegistry = Depends(get_registry)) -> dict:
    project = registry.create_project(body.name, body.description or "", owner)
    return _out(project, registry)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str = ProjectIdPath, owner: str = Depends(get_principal),
                registry: BaseRegistry = Depends(get_registry)) -> dict:
    return _out(registry.get_project(project_id, owner), registry)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(body: ProjectUpdate, project_id: str = ProjectIdPath, owner: str = Depends(get_principal),
                   registry: BaseRegistry = Depends(get_registry)) -> dict:
    return _out(registry.update_project(project_id, body.name, body.description, owner), registry)


@router.delete("/{project_id}", status_code=204)
def delete_project(body: ProjectDelete, project_id: str = ProjectIdPath, owner: str = Depends(get_principal),
                   registry: BaseRegistry = Depends(get_registry),
                   manager: InvestigationManager = Depends(get_manager)) -> None:
    """Deletes the project's graph, files and saved investigations. Requires the exact project name."""
    registry.get_project(project_id, owner)  # ownership first: another user's project is a 404, never a 409
    if manager.running(project_id):
        raise HTTPException(409, "An investigation is running in this project. Wait for it to finish before deleting.")
    registry.delete_project(project_id, body.confirm_name, owner)
    forget_project(project_id)
    manager.forget_project(project_id)
