"""Response schemas for health and graph endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BackendHealth(BaseModel):
    status: Literal["ok"]
    version: str
    uptime_seconds: float


class DatabaseHealth(BaseModel):
    status: Literal["connected", "unavailable", "not_configured"]
    latency_ms: float | None
    message: str | None


class LLMStatus(BaseModel):
    provider: str = Field(description="ollama | anthropic | none")
    model: str | None
    status: Literal["ready", "configured", "model_missing", "unreachable", "not_configured", "error"]
    reachable: bool | None
    model_available: bool | None
    message: str


class ConfigInfo(BaseModel):
    max_upload_mb: int
    max_files_per_upload: int
    llm_configured: bool
    ai_required: bool = True
    embedding_model: str | None
    llm: LLMStatus


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    backend: BackendHealth
    database: DatabaseHealth
    config: ConfigInfo
    timestamp: str


class GraphStats(BaseModel):
    nodes: dict[str, int]
    relationships: int


class GraphNode(BaseModel):
    id: str
    type: Literal["paper", "method", "dataset"]
    label: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    score: float | None = None


class GraphOverview(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
