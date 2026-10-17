"""Request/response schemas for /api/investigations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from researchmind.accounts import LANGUAGES

MIN_QUESTION_CHARS = 10
MAX_QUESTION_CHARS = 1000
MAX_REQUIREMENTS_CHARS = 3000
PAPER_ID_PATTERN = r"^p_[0-9a-f]{12}$"

InvestigationStatus = Literal["queued", "running", "completed", "failed"]
Language = Literal[tuple(LANGUAGES)]  # type: ignore[valid-type]


class InvestigationRequest(BaseModel):
    question: str = Field(..., description="The research question to investigate.")
    paper_id: str = Field(..., pattern=PAPER_ID_PATTERN,
                          description="The one paper to analyse. Each investigation reads exactly one paper; "
                                      "no other paper of the account is consulted.")
    wait: bool = Field(False, description="false: respond immediately (202) and poll GET .../investigations/{id}. "
                                          "true: respond when the investigation finishes (up to the time limit).")
    requirements: str | None = Field(None, description="Optional user-provided project requirements or context. "
                                                        "Treated as [R], never as published evidence.")
    language: Language | None = Field(None, description="Language of the report; defaults to the account's language.")

    @field_validator("requirements")
    @classmethod
    def _check_requirements(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if len(v) > MAX_REQUIREMENTS_CHARS:
            raise ValueError(f"requirements must be at most {MAX_REQUIREMENTS_CHARS} characters")
        return v or None

    @field_validator("question")
    @classmethod
    def _check_question(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v) < MIN_QUESTION_CHARS:
            raise ValueError(f"the question must be at least {MIN_QUESTION_CHARS} characters")
        if len(v) > MAX_QUESTION_CHARS:
            raise ValueError(f"the question must be at most {MAX_QUESTION_CHARS} characters")
        return v


class Source(BaseModel):
    n: int
    chunk_id: str
    paper_id: str
    paper_title: str | None
    year: int | None = None
    page: int | None
    section: str | None = None
    quote: str
    cited_in_report: bool


class Finding(BaseModel):
    type: str
    text: str
    paper_id: str
    paper_title: str | None
    year: int | None = None
    page: int | None
    relevance: float | None = None
    citations: list[int]


class ComparisonSide(BaseModel):
    text: str
    paper_id: str
    paper_title: str | None
    page: int | None
    citation: int


class Comparison(BaseModel):
    kind: Literal["contradiction", "related"]
    score: float
    a: ComparisonSide
    b: ComparisonSide
    note: str


class EntityPaper(BaseModel):
    paper_id: str
    paper_title: str | None
    citation: int


class EntityComparison(BaseModel):
    entity: str
    type: Literal["method", "dataset"]
    papers: list[EntityPaper]


class GapEvidence(BaseModel):
    citation: int
    paper_id: str
    paper_title: str | None
    page: int | None
    quote: str


class Gap(BaseModel):
    id: str
    title: str
    type: str
    rationale: str
    score: float | None
    status: Literal["candidate"]
    evidence: list[GapEvidence]
    citations: list[int]
    note: str
    support_papers: int = Field(2, description="Distinct relevant papers whose verified evidence supports the gap.")


class Inference(BaseModel):
    text: str = Field(description="A model-generated hypothesis: an inference, not a finding stated in the papers.")
    citations: list[int]


class Limitation(BaseModel):
    text: str
    kind: Literal["limitation", "future_work"]
    paper_id: str
    paper_title: str | None
    page: int | None
    citations: list[int]


class Confidence(BaseModel):
    level: Literal["low", "moderate", "high"]
    reasons: list[str]
    uncertainties: list[str]
    narrative: str | None


class PaperRef(BaseModel):
    paper_id: str
    title: str | None
    year: int | None = None
    sources: int


class Step(BaseModel):
    tool: str
    args: dict
    summary: str
    source: str
    ok: bool


class InvestigationResultBody(BaseModel):
    mode: Literal["llm", "offline"]
    evidence_found: bool = Field(description="False when no stored evidence reached the relevance threshold.")
    summary: str
    report_markdown: str
    findings: list[Finding]
    comparisons: list[Comparison]
    method_comparison: list[EntityComparison]
    gaps: list[Gap]
    inferences: list[Inference] = []
    open_questions: list[str] = Field([], description="Parts of the question the evidence does not answer.")
    limitations: list[Limitation]
    confidence: Confidence
    sources: list[Source]
    papers: list[PaperRef]
    steps: list[Step]
    warnings: list[str]


class ProgressEvent(BaseModel):
    type: str
    message: str
    tool: str | None = None
    at: float = Field(description="Seconds since the investigation started.")


class InvestigationError(BaseModel):
    code: str
    message: str


class InvestigationResponse(BaseModel):
    id: str
    project_id: str
    question: str
    status: InvestigationStatus
    mode: Literal["llm", "offline"] | None
    llm_configured: bool
    provider: str | None = Field(None, description="LLM provider used (ollama, anthropic) when mode is llm.")
    model: str | None = None
    requirements: str | None = None
    paper_ids: list[str] | None = Field(None, description="The paper the investigation analysed (one id).")
    paper_title: str | None = None
    language: str | None = None
    created_at: str
    started_at: str | None
    finished_at: str | None
    duration_seconds: float | None
    progress: list[ProgressEvent]
    result: InvestigationResultBody | None
    error: InvestigationError | None


class InvestigationSummary(BaseModel):
    id: str
    project_id: str
    question: str
    status: InvestigationStatus
    provider: str | None = None
    model: str | None = None
    mode: Literal["llm", "offline"] | None
    paper_title: str | None = None
    created_at: str
    duration_seconds: float | None


class InvestigationList(BaseModel):
    investigations: list[InvestigationSummary]
    total: int
    limit: int
    offset: int
