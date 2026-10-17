"""Project workspaces and saved investigations.

Isolation strategy: ONE FALKORDB GRAPH PER PROJECT.
  Every paper, chunk, page, statement, entity and embedding of a project lives in that project's
  own graph, so every tool, vector search and Cypher query (including the agent's free-form
  graph_query) can only see that project's data. On disk, each project has its own folder for
  uploaded PDFs, page text and extraction dumps.

Registry: a separate graph `<FALKORDB_GRAPH>_registry` holds
  (:Project {id, name, description, owner_id, graph_name, data_dir, created_at, updated_at})
  (:Investigation {id, project_id, owner_id, question, status, ..., result_json})
  (:Project)-[:HAS_INVESTIGATION]->(:Investigation)

Migration: the pre-existing graph `<FALKORDB_GRAPH>` and the legacy data folders become the
"Default project" (id "default") without copying anything.

Ownership: every project has an owner_id - the id of the signed-in user (accounts.py) who
created it. `authorize()` is checked on every project lookup, and a project of another user is
reported as "not found" so its existence is never revealed. Each new account gets its own first
project ("workspace") at sign-up. The legacy Default project belongs to LOCAL_OWNER, which is only
used by the command-line tools; no signed-in user can reach it.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import get_settings

DEFAULT_PROJECT_ID = "default"
LOCAL_OWNER = "local"
PROJECT_ID = re.compile(r"^(default|prj_[0-9a-f]{10})$")
INVESTIGATION_ID = re.compile(r"^inv_[0-9a-f]{12}$")
MAX_NAME = 80
MAX_DESCRIPTION = 500


class ProjectError(Exception):
    """User-facing project error. `code` maps to an HTTP status in the API."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code  # not_found | invalid | conflict | forbidden


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Project:
    id: str
    name: str
    description: str
    owner_id: str
    graph_name: str
    data_dir: str
    created_at: str
    updated_at: str

    @property
    def root(self) -> Path:
        return Path(self.data_dir)

    @property
    def upload_dir(self) -> Path:
        return self.root / "uploads"

    @property
    def documents_dir(self) -> Path:
        return self.root / "documents"

    @property
    def processed_dir(self) -> Path:
        return self.root / "processed"

    @property
    def is_default(self) -> bool:
        return self.id == DEFAULT_PROJECT_ID

    def public(self) -> dict:
        """API view: never exposes graph names or filesystem paths."""
        return {"id": self.id, "name": self.name, "description": self.description, "owner_id": self.owner_id,
                "created_at": self.created_at, "updated_at": self.updated_at, "is_default": self.is_default}


def authorize(project: Project, owner_id: str, action: str) -> None:
    """Single authorization hook (actions: read | write | delete): only the owner may touch a project."""
    if not owner_id or project.owner_id != owner_id:
        raise ProjectError("Project not found.", "not_found")  # do not reveal other users' projects


def validate_name(name: str) -> str:
    name = " ".join((name or "").split())
    if not name:
        raise ProjectError("Project name is required.", "invalid")
    if len(name) > MAX_NAME:
        raise ProjectError(f"Project name must be at most {MAX_NAME} characters.", "invalid")
    return name


def _project_paths(project_id: str) -> tuple[str, str]:
    s = get_settings()
    if project_id == DEFAULT_PROJECT_ID:  # legacy layout: <data>/uploads, <data>/documents, ...
        return s.graph_name, str(s.data_dir)
    return f"{s.graph_name}__{project_id}", str(s.data_dir / "projects" / project_id)


def _new_project(name: str, description: str, owner_id: str, project_id: str | None = None) -> Project:
    pid = project_id or "prj_" + uuid.uuid4().hex[:10]
    graph_name, data_dir = _project_paths(pid)
    now = _now()
    return Project(id=pid, name=validate_name(name), description=(description or "").strip()[:MAX_DESCRIPTION],
                   owner_id=owner_id, graph_name=graph_name, data_dir=data_dir, created_at=now, updated_at=now)


INVESTIGATION_FIELDS = ("id", "project_id", "owner_id", "question", "requirements", "status", "mode", "provider", "model",
                        "use_llm", "created_at", "started_at", "finished_at", "duration_seconds", "error_code",
                        "error_message", "result_json", "progress_json", "paper_ids_json", "paper_title", "language")


class BaseRegistry:
    """Shared validation and project lifecycle on top of a small storage interface."""

    # storage interface -------------------------------------------------------
    def _get_project(self, project_id: str) -> Project | None: ...
    def _put_project(self, p: Project) -> None: ...
    def _all_projects(self) -> list[Project]: ...
    def _remove_project(self, project_id: str) -> None: ...
    def _put_investigation(self, rec: dict) -> None: ...
    def _get_investigation(self, inv_id: str) -> dict | None: ...
    def _list_investigations(self, project_id: str, limit: int, offset: int) -> tuple[list[dict], int]: ...
    def _remove_investigation(self, inv_id: str) -> None: ...
    def _mark_interrupted(self) -> int: ...
    def _drop_project_graph(self, p: Project) -> None: ...

    # projects ----------------------------------------------------------------
    def ensure_default(self) -> Project:
        p = self._get_project(DEFAULT_PROJECT_ID)
        if p is None:
            p = _new_project("Default project", "Papers uploaded before projects existed.", LOCAL_OWNER, DEFAULT_PROJECT_ID)
            self._put_project(p)
        return p

    def ensure_workspace(self, owner_id: str, name: str = "My research") -> Project:
        """The user's first project, created when they have none (at sign-up)."""
        mine = [p for p in self._all_projects() if p.owner_id == owner_id]
        if mine:
            return min(mine, key=lambda p: p.created_at)
        p = _new_project(name, "", owner_id)
        self._put_project(p)
        return p

    def purge_owner(self, owner_id: str) -> int:
        """Delete every project of a user, with its graph, files and saved investigations (account deletion)."""
        mine = [p for p in self._all_projects() if p.owner_id == owner_id and not p.is_default]
        for p in mine:
            self._drop_project_graph(p)
            root = p.root
            if root.exists() and root.resolve().is_relative_to((get_settings().data_dir / "projects").resolve()):
                shutil.rmtree(root, ignore_errors=True)
            self._remove_project(p.id)
        return len(mine)

    def list_projects(self, owner_id: str = LOCAL_OWNER) -> list[Project]:
        if owner_id == LOCAL_OWNER:
            self.ensure_default()
        return sorted((p for p in self._all_projects() if p.owner_id == owner_id),
                      key=lambda p: (not p.is_default, p.name.lower()))

    def get_project(self, project_id: str, owner_id: str = LOCAL_OWNER) -> Project:
        if not PROJECT_ID.match(project_id or ""):
            raise ProjectError("Project not found.", "not_found")
        if project_id == DEFAULT_PROJECT_ID and owner_id == LOCAL_OWNER:
            self.ensure_default()
        p = self._get_project(project_id)
        if p is None:
            raise ProjectError("Project not found.", "not_found")
        authorize(p, owner_id, "read")
        return p

    def _check_unique(self, name: str, owner_id: str, exclude: str | None = None) -> None:
        if any(p.name.lower() == name.lower() and p.id != exclude for p in self.list_projects(owner_id)):
            raise ProjectError(f"A project named '{name}' already exists.", "conflict")

    def create_project(self, name: str, description: str = "", owner_id: str = LOCAL_OWNER) -> Project:
        p = _new_project(name, description, owner_id)
        self._check_unique(p.name, owner_id)
        self._put_project(p)
        return p

    def update_project(self, project_id: str, name: str | None = None, description: str | None = None,
                       owner_id: str = LOCAL_OWNER) -> Project:
        p = self.get_project(project_id, owner_id)
        authorize(p, owner_id, "write")
        if name is not None:
            p.name = validate_name(name)
            self._check_unique(p.name, owner_id, exclude=p.id)
        if description is not None:
            p.description = description.strip()[:MAX_DESCRIPTION]
        p.updated_at = _now()
        self._put_project(p)
        return p

    def delete_project(self, project_id: str, confirm_name: str, owner_id: str = LOCAL_OWNER) -> None:
        p = self.get_project(project_id, owner_id)
        authorize(p, owner_id, "delete")
        if p.is_default:
            raise ProjectError("The Default project holds data from before projects existed and cannot be deleted. "
                               "Delete its papers individually instead.", "forbidden")
        if " ".join((confirm_name or "").split()) != p.name:
            raise ProjectError("Type the exact project name to confirm deletion.", "invalid")
        self._drop_project_graph(p)
        root = p.root
        if root.exists() and root.resolve().is_relative_to((get_settings().data_dir / "projects").resolve()):
            shutil.rmtree(root, ignore_errors=True)
        self._remove_project(p.id)  # also removes its saved investigations

    # investigations ----------------------------------------------------------
    def save_investigation(self, rec: dict) -> None:
        self._put_investigation({k: rec.get(k) for k in INVESTIGATION_FIELDS})

    def get_investigation(self, project_id: str, inv_id: str) -> dict | None:
        if not INVESTIGATION_ID.match(inv_id or ""):
            return None
        rec = self._get_investigation(inv_id)
        return rec if rec and rec.get("project_id") == project_id else None  # never across projects

    def list_investigations(self, project_id: str, limit: int = 20, offset: int = 0) -> tuple[list[dict], int]:
        return self._list_investigations(project_id, limit, offset)

    def delete_investigation(self, project_id: str, inv_id: str) -> bool:
        if not self.get_investigation(project_id, inv_id):
            return False
        self._remove_investigation(inv_id)
        return True

    def mark_interrupted(self) -> int:
        """Investigations left queued/running by a previous process can never finish: mark them failed."""
        return self._mark_interrupted()


INTERRUPTED = ("interrupted", "The API restarted before this investigation finished. Run it again.")


class FalkorRegistry(BaseRegistry):
    def __init__(self, db, graph_name: str | None = None):
        self.db = db
        self.graph_name = graph_name or f"{get_settings().graph_name}_registry"
        self.graph = db.select_graph(self.graph_name)
        self._lock = threading.Lock()
        for label, prop in (("Project", "id"), ("Investigation", "id"), ("Investigation", "project_id")):
            try:
                self.graph.create_node_range_index(label, prop)
            except Exception as e:  # already indexed
                if "already indexed" not in str(e).lower():
                    raise

    def _q(self, cypher: str, params: dict | None = None, read_only: bool = False) -> list[dict]:
        fn = self.graph.ro_query if read_only else self.graph.query
        r = fn(cypher, params or {})
        cols = [h[1] if isinstance(h, (list, tuple)) else h for h in (r.header or [])]
        cols = [c.decode() if isinstance(c, bytes) else c for c in cols]
        return [dict(zip(cols, row)) for row in r.result_set]

    def _get_project(self, project_id):
        rows = self._q("MATCH (p:Project {id: $id}) RETURN p", {"id": project_id}, read_only=True)
        return Project(**{k: rows[0]["p"].properties.get(k) for k in Project.__dataclass_fields__}) if rows else None

    def _put_project(self, p):
        with self._lock:
            self._q("MERGE (x:Project {id: $id}) SET x += $props", {"id": p.id, "props": asdict(p)})

    def _all_projects(self):
        return [Project(**{k: r["p"].properties.get(k) for k in Project.__dataclass_fields__})
                for r in self._q("MATCH (p:Project) RETURN p", read_only=True)]

    def _remove_project(self, project_id):
        self._q("MATCH (p:Project {id: $id}) OPTIONAL MATCH (p)-[:HAS_INVESTIGATION]->(i) DETACH DELETE i, p", {"id": project_id})
        self._q("MATCH (i:Investigation {project_id: $id}) DETACH DELETE i", {"id": project_id})

    def _drop_project_graph(self, p):
        if p.graph_name in self.db.list_graphs():
            self.db.select_graph(p.graph_name).delete()

    def _put_investigation(self, rec):
        props = {k: v for k, v in rec.items() if v is not None}
        self._q("""MERGE (i:Investigation {id: $id}) SET i += $props
                   WITH i MATCH (p:Project {id: $pid}) MERGE (p)-[:HAS_INVESTIGATION]->(i)""",
                {"id": rec["id"], "props": props, "pid": rec["project_id"]})

    def _get_investigation(self, inv_id):
        rows = self._q("MATCH (i:Investigation {id: $id}) RETURN i", {"id": inv_id}, read_only=True)
        return dict(rows[0]["i"].properties) if rows else None

    def _list_investigations(self, project_id, limit, offset):
        total = self._q("MATCH (i:Investigation {project_id: $pid}) RETURN count(i) AS n", {"pid": project_id}, read_only=True)[0]["n"]
        rows = self._q("""MATCH (i:Investigation {project_id: $pid})
                          RETURN i.id AS id, i.project_id AS project_id, i.question AS question, i.status AS status,
                                 i.mode AS mode, i.provider AS provider, i.model AS model, i.created_at AS created_at,
                                 i.paper_title AS paper_title,
                                 i.duration_seconds AS duration_seconds
                          ORDER BY i.created_at DESC SKIP $offset LIMIT $limit""",
                       {"pid": project_id, "offset": offset, "limit": limit}, read_only=True)
        return rows, total

    def _remove_investigation(self, inv_id):
        self._q("MATCH (i:Investigation {id: $id}) DETACH DELETE i", {"id": inv_id})

    def _mark_interrupted(self):
        rows = self._q("""MATCH (i:Investigation) WHERE i.status IN ['queued', 'running']
                          SET i.status = 'failed', i.error_code = $code, i.error_message = $msg, i.finished_at = $now
                          RETURN count(i) AS n""", {"code": INTERRUPTED[0], "msg": INTERRUPTED[1], "now": _now()})
        return rows[0]["n"] if rows else 0


class MemoryRegistry(BaseRegistry):
    """In-process registry for tests (and tools that do not need persistence)."""

    def __init__(self):
        self.projects: dict[str, Project] = {}
        self.investigations: dict[str, dict] = {}
        self.dropped_graphs: list[str] = []

    def _get_project(self, project_id):
        p = self.projects.get(project_id)
        return Project(**asdict(p)) if p else None

    def _put_project(self, p):
        self.projects[p.id] = Project(**asdict(p))

    def _all_projects(self):
        return [Project(**asdict(p)) for p in self.projects.values()]

    def _remove_project(self, project_id):
        self.projects.pop(project_id, None)
        for k in [k for k, v in self.investigations.items() if v["project_id"] == project_id]:
            del self.investigations[k]

    def _drop_project_graph(self, p):
        self.dropped_graphs.append(p.graph_name)

    def _put_investigation(self, rec):
        self.investigations[rec["id"]] = {**self.investigations.get(rec["id"], {}), **{k: v for k, v in rec.items() if v is not None}}

    def _get_investigation(self, inv_id):
        rec = self.investigations.get(inv_id)
        return dict(rec) if rec else None

    def _list_investigations(self, project_id, limit, offset):
        items = sorted((v for v in self.investigations.values() if v["project_id"] == project_id),
                       key=lambda v: v.get("created_at") or "", reverse=True)
        keys = ("id", "project_id", "question", "status", "mode", "provider", "model", "created_at", "duration_seconds",
                "paper_title")
        return [{k: v.get(k) for k in keys} for v in items[offset:offset + limit]], len(items)

    def _remove_investigation(self, inv_id):
        self.investigations.pop(inv_id, None)

    def _mark_interrupted(self):
        n = 0
        for v in self.investigations.values():
            if v.get("status") in ("queued", "running"):
                v.update(status="failed", error_code=INTERRUPTED[0], error_message=INTERRUPTED[1], finished_at=_now())
                n += 1
        return n


def encode_json(value) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))
