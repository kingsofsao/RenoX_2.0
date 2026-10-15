"""Schemas for /api/projects."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    description: str | None = Field(None, max_length=500)


class ProjectDelete(BaseModel):
    confirm_name: str = Field(..., description="Must equal the project's current name exactly.")


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str
    created_at: str
    updated_at: str
    is_default: bool
    paper_count: int | None = None
    investigation_count: int | None = None


class ProjectList(BaseModel):
    projects: list[ProjectOut]
