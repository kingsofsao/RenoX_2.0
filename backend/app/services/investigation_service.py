"""Runs investigations in a bounded worker pool, each over one paper of one user's project, and saves them.

Investigations are AI-driven (AI_REQUIRED, default on): the LLM reads evidence that the agent
retrieves from the paper's knowledge graph through the MCP tools. If the AI service is not
configured or fails, the investigation fails with a clear message instead of silently switching to
an extractive offline report. Investigations take seconds to minutes, so they run in background threads.
Live progress is kept in memory for polling; the investigation record (question, status, report,
citations, structured result, timestamps) is saved to the project registry when it is submitted,
when it starts and when it finishes, so saved results survive restarts.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

from researchmind.agent import Investigator
from researchmind.config import get_settings
from researchmind.graph import GraphStore
from researchmind.investigation import build_structured
from researchmind.llm import LLMUnavailable
from researchmind.projects import BaseRegistry, Project, encode_json

from ..config import get_api_settings
from ..database import reset_store

log = logging.getLogger("researchmind.api.investigations")

MAX_EVENTS = 300


class InvestigationBusy(Exception):
    """All investigation workers are in use."""


class UserBusy(InvestigationBusy):
    """This user already has the maximum number of investigations running."""


class AIUnavailable(Exception):
    """The AI service is not configured, so an AI investigation cannot start."""


AI_NOT_CONFIGURED = ("The AI service is not configured on this server, so investigations cannot run. "
                     "Please contact the administrator.")
# What users see when the model fails mid-run; the technical detail goes to the server log only.
AI_ERRORS = {
    "timeout": "The AI model took too long to answer. Please try again; a shorter, more specific question helps.",
    "malformed": "The AI model did not return a usable, cited answer. Please try again or rephrase the question.",
    "refusal": "The AI model declined to answer this question. Please rephrase it.",
}
AI_ERROR_DEFAULT = "The AI service is unavailable right now. Please try again in a few minutes."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    question: str
    use_llm: bool
    project_id: str = "default"
    owner_id: str = "local"
    requirements: str | None = None
    paper_ids: list[str] | None = None  # the one paper analysed
    paper_title: str | None = None
    language: str = "en"
    provider: str | None = None
    model: str | None = None
    created_at: str = field(default_factory=_now)
    status: str = "queued"
    mode: str | None = None
    llm_configured: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    progress: list[dict] = field(default_factory=list)
    result: dict | None = None
    error: dict | None = None
    done: threading.Event = field(default_factory=threading.Event)
    registry: BaseRegistry | None = field(default=None, repr=False)
    _t0: float = 0.0

    def add_event(self, event: dict) -> None:
        kind = event.get("type", "status")
        tool = event.get("tool")
        if kind == "tool_call":
            message = f"Calling MCP tool {tool}"
        elif kind == "tool_result":
            message = f"{tool}: {event.get('summary', 'done')}"
        else:
            message = str(event.get("message", ""))
        message = message if len(message) <= 300 else message[:299] + "…"
        if len(self.progress) < MAX_EVENTS:
            self.progress.append({"type": kind, "message": message, "tool": tool,
                                  "at": round(time.monotonic() - self._t0, 2) if self._t0 else 0.0})

    def record(self) -> dict:
        """The persisted form (see projects.INVESTIGATION_FIELDS)."""
        return {"id": self.id, "project_id": self.project_id, "owner_id": self.owner_id, "question": self.question,
                "requirements": self.requirements, "status": self.status, "mode": self.mode, "provider": self.provider,
                "model": self.model, "use_llm": self.use_llm, "created_at": self.created_at, "started_at": self.started_at,
                "finished_at": self.finished_at, "duration_seconds": self.duration_seconds,
                "error_code": (self.error or {}).get("code"), "error_message": (self.error or {}).get("message"),
                "result_json": encode_json(self.result) if self.result is not None else None,
                "paper_ids_json": encode_json(self.paper_ids) if self.paper_ids else None,
                "paper_title": self.paper_title, "language": self.language,
                "progress_json": encode_json(self.progress)}

    def save(self) -> None:
        if self.registry is None:
            return
        try:
            self.registry.save_investigation(self.record())
        except Exception as e:  # saving must never break the investigation itself
            log.warning("Could not save investigation %s: %s", self.id, e.__class__.__name__)

    def to_dict(self) -> dict:
        return {"id": self.id, "project_id": self.project_id, "question": self.question, "status": self.status, "mode": self.mode,
                "llm_configured": self.llm_configured, "provider": self.provider, "model": self.model,
                "requirements": self.requirements, "paper_ids": self.paper_ids, "paper_title": self.paper_title,
                "language": self.language, "created_at": self.created_at,
                "started_at": self.started_at, "finished_at": self.finished_at, "duration_seconds": self.duration_seconds,
                "progress": list(self.progress), "result": self.result, "error": self.error}

    def summary(self) -> dict:
        return {"id": self.id, "project_id": self.project_id, "question": self.question, "status": self.status, "mode": self.mode,
                "provider": self.provider, "model": self.model, "paper_title": self.paper_title,
                "created_at": self.created_at, "duration_seconds": self.duration_seconds}


class InvestigationManager:
    def __init__(self, max_concurrent: int, time_budget_s: float, keep: int = 50,
                 investigator_factory: Callable[..., Investigator] = Investigator):
        self.investigator_factory = investigator_factory  # tests inject fake tools/LLMs here
        self.max_concurrent = max(1, max_concurrent)
        self.time_budget_s = time_budget_s
        self.keep = keep
        self._executor = ThreadPoolExecutor(max_workers=self.max_concurrent, thread_name_prefix="investigation")
        self._jobs: OrderedDict[str, Job] = OrderedDict()
        self._lock = threading.Lock()

    def submit(self, question: str, store: GraphStore, use_llm: bool = True, requirements: str | None = None,
               project: Project | None = None, registry: BaseRegistry | None = None,
               paper_ids: list[str] | None = None, paper_title: str | None = None, language: str = "en",
               owner_id: str | None = None) -> Job:
        api, s = get_api_settings(), get_settings()
        if api.ai_required and use_llm and not s.has_llm:
            raise AIUnavailable(AI_NOT_CONFIGURED)
        owner = owner_id or (project.owner_id if project else "local")
        with self._lock:
            active = [j for j in self._jobs.values() if j.status in ("queued", "running")]
            if sum(j.owner_id == owner for j in active) >= api.investigations_per_user:
                raise UserBusy()
            if len(active) >= self.max_concurrent:
                raise InvestigationBusy()
            job = Job(id="inv_" + uuid.uuid4().hex[:12], question=question, use_llm=use_llm, requirements=requirements,
                      paper_ids=paper_ids or None, paper_title=paper_title, language=language,
                      llm_configured=s.has_llm, registry=registry,
                      project_id=project.id if project else "default", owner_id=owner)
            if use_llm and s.has_llm:  # expected provider; confirmed when the run finishes
                job.mode, job.provider = "llm", s.resolved_provider
                job.model = s.llm_model or (s.anthropic_model if job.provider == "anthropic" else None)
            self._jobs[job.id] = job
            while len(self._jobs) > self.keep:
                oldest = next(iter(self._jobs))
                if self._jobs[oldest].status in ("queued", "running"):
                    break
                self._jobs.pop(oldest)
        job.save()
        self._executor.submit(self._run, job, store)
        return job

    def get(self, job_id: str, project_id: str | None = None) -> Job | None:
        job = self._jobs.get(job_id)
        if job is not None and project_id is not None and job.project_id != project_id:
            return None  # never across projects
        return job

    def forget_project(self, project_id: str) -> None:
        """Drop in-memory results of a deleted project, so nothing of it stays reachable."""
        with self._lock:
            for k in [k for k, j in self._jobs.items() if j.project_id == project_id]:
                del self._jobs[k]

    def running(self, project_id: str) -> bool:
        return any(j.project_id == project_id and j.status in ("queued", "running") for j in self._jobs.values())

    def recent(self, limit: int = 20) -> list[Job]:
        return list(reversed(self._jobs.values()))[:limit]

    def _run(self, job: Job, store: GraphStore) -> None:
        job._t0 = time.monotonic()
        job.started_at, job.status = _now(), "running"
        job.save()
        try:
            investigator = self.investigator_factory(store, use_llm=job.use_llm, time_budget_s=self.time_budget_s,
                                                     paper_ids=job.paper_ids, language=job.language,
                                                     require_llm=get_api_settings().ai_required and job.use_llm)
            job.add_event({"type": "status", "message": f"Analysing one paper: {job.paper_title or 'selected paper'}"})
            job.mode, job.provider, job.model = investigator.mode, investigator.provider, getattr(investigator.llm, "model", None)
            if investigator.llm:
                job.add_event({"type": "status", "message": f"AI model: {job.model or job.provider}"})
            result = investigator.run(job.question, on_event=job.add_event, requirements=job.requirements)
            job.add_event({"type": "status", "message": "Building structured report and verifying sources"})
            structured = build_structured(result, lookup=lambda ids: investigator.tools.get_evidence(ids)["evidence"],
                                          corpus_size=len(investigator.tools.list_papers()["papers"]),
                                          scoped=True, paper_ids=job.paper_ids)
            job.mode = result.mode
            if result.mode == "offline":
                job.provider, job.model = None, None
            job.result = {"mode": result.mode, "report_markdown": result.report_markdown, "steps": result.steps,
                          "warnings": result.warnings, **structured}
            job.status = "completed"
        except LLMUnavailable as e:
            log.warning("Investigation %s: AI service failed (%s): %s", job.id, e.code, e)  # detail stays in the log
            message = AI_NOT_CONFIGURED if e.code == "not_configured" else AI_ERRORS.get(e.code, AI_ERROR_DEFAULT)
            job.status, job.error = "failed", {"code": "ai_unavailable", "message": message}
        except (RedisConnectionError, RedisTimeoutError) as e:
            log.warning("FalkorDB connection lost during investigation %s: %s", job.id, e.__class__.__name__)
            reset_store()
            job.status, job.error = "failed", {"code": "database_unavailable",
                                               "message": "Lost connection to the graph database during the investigation. Please retry."}
        except Exception:
            log.exception("Investigation %s failed", job.id)  # details stay in the server log
            job.status, job.error = "failed", {"code": "investigation_failed",
                                               "message": "The investigation failed due to an internal error. Please try again."}
        finally:
            job.finished_at = _now()
            job.duration_seconds = round(time.monotonic() - job._t0, 2)
            job.add_event({"type": "done" if job.status == "completed" else "error",
                           "message": "Investigation complete" if job.status == "completed" else job.error["message"]})
            job.save()
            job.done.set()


_manager: InvestigationManager | None = None
_manager_lock = threading.Lock()


def get_manager() -> InvestigationManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            s = get_api_settings()
            _manager = InvestigationManager(s.investigation_max_concurrent, s.investigation_timeout_s)
        return _manager


def record_to_response(rec: dict) -> dict:
    """A saved investigation record in InvestigationResponse shape."""
    def load(key, default):
        try:
            return json.loads(rec[key]) if rec.get(key) else default
        except (TypeError, ValueError):
            return default
    error = ({"code": rec.get("error_code") or "investigation_failed", "message": rec.get("error_message") or "Failed."}
             if rec.get("status") == "failed" else None)
    return {"id": rec["id"], "project_id": rec["project_id"], "question": rec.get("question") or "",
            "status": rec.get("status") or "failed", "mode": rec.get("mode"),
            "llm_configured": bool(rec.get("use_llm")), "provider": rec.get("provider"), "model": rec.get("model"),
            "requirements": rec.get("requirements"), "paper_ids": load("paper_ids_json", None),
            "paper_title": rec.get("paper_title"), "language": rec.get("language"),
            "created_at": rec.get("created_at") or "",
            "started_at": rec.get("started_at"), "finished_at": rec.get("finished_at"),
            "duration_seconds": rec.get("duration_seconds"), "progress": load("progress_json", []),
            "result": load("result_json", None), "error": error}
