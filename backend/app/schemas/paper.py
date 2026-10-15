"""Response schemas for the papers API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PaperStatus = Literal["processed", "failed"]
UploadStatus = Literal["processed", "duplicate", "failed", "rejected"]


class PaperSummary(BaseModel):
    id: str
    title: str | None = Field(None, description="Detected title, or null when it could not be identified")
    display_title: str = Field(description="Title, or the file name when the title is unknown")
    filename: str | None
    status: PaperStatus
    page_count: int | None = None
    authors: list[str] = []
    year: int | None = None
    file_size: int | None = None
    error: str | None = None
    error_code: str | None = None
    updated_at: str | None = None


class PaperCounts(BaseModel):
    total: int
    processed: int
    failed: int


class PaperListResponse(BaseModel):
    papers: list[PaperSummary]
    counts: PaperCounts
    total_matching: int
    limit: int
    offset: int


class EntityRef(BaseModel):
    name: str
    page: int | None = None


class KnowledgeSummary(BaseModel):
    extractor: str | None = None
    methods: list[EntityRef] = []
    datasets: list[EntityRef] = []
    claims: int = 0
    findings: int = 0
    limitations: int = 0
    chunks: int = 0
    sections: list[str] = []


class PageText(BaseModel):
    page: int
    text: str
    chars: int


class Pagination(BaseModel):
    page: int
    page_size: int
    total_pages: int


class PaperDetail(PaperSummary):
    sha256: str | None = None
    abstract: str | None = None
    title_detected: bool | None = None
    ingested_at: str | None = None
    pdf_metadata: dict[str, str] = {}
    knowledge: KnowledgeSummary | None = None


class PaperDetailResponse(BaseModel):
    paper: PaperDetail
    pages: list[PageText]
    pagination: Pagination
    text_available: bool


class UploadResult(BaseModel):
    filename: str
    status: UploadStatus
    paper_id: str | None = None
    title: str | None = None
    page_count: int | None = None
    message: str
    error_code: str | None = None


class UploadSummary(BaseModel):
    received: int
    processed: int
    duplicate: int
    failed: int
    rejected: int


class UploadResponse(BaseModel):
    results: list[UploadResult]
    summary: UploadSummary
