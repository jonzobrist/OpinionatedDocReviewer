from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MetaReviewStatus = Literal["queued", "running", "completed", "failed"]
MetaReviewResolution = Literal["reused", "created"]
MetaReviewVerdict = Literal["clean", "review_needed", "problems"]


class MetaReviewCreate(BaseModel):
    document_version_id: int = Field(gt=0)
    review_job_id: int | None = Field(default=None, gt=0)
    force: bool = False


class MetaReviewEnsureRequest(BaseModel):
    document_version_id: int = Field(gt=0)
    review_job_id: int | None = Field(default=None, gt=0)
    force: bool = False


class MetaReviewErrorDetailRead(BaseModel):
    code: str
    message: str
    retryable: bool = True


class MetaCommentSourceRead(BaseModel):
    id: int
    comment_id: int
    reviewer_name: str
    reviewer_id: int
    original_comment_text: str

    model_config = ConfigDict(from_attributes=True)


class MetaCommentRead(BaseModel):
    id: int
    content: str
    category: str
    priority: str
    impact: str
    effort: str
    confidence: float
    why_now: str | None = None
    recommended_change: str | None = None
    verification_step: str | None = None
    status: str
    assignee: str | None = None
    due_at: str | None = None
    rank_score: float
    start_offset: int
    end_offset: int
    order_index: int
    is_unsynthesized: bool
    sources: list[MetaCommentSourceRead]

    model_config = ConfigDict(from_attributes=True)


class MetaAttentionPointRead(BaseModel):
    meta_comment_id: int
    location: str
    reason: str
    priority: str
    start_offset: int
    end_offset: int
    source_comment_ids: list[int] = Field(default_factory=list)


class MetaReviewSummaryRead(BaseModel):
    verdict: MetaReviewVerdict
    # One-sentence human-readable rationale for the verdict. Emitted by
    # the LLM synthesis pass when available; None when the rule-based
    # fallback runs (no LLM provider configured, provider down, etc.).
    bottom_line: str | None = None
    # Up to three short blocker summaries the LLM picked as the most
    # critical issues driving the verdict, independent of attention_points
    # which are ranked by score. Empty list in the fallback path.
    top_blockers: list[str] = Field(default_factory=list)
    attention_points: list[MetaAttentionPointRead] = Field(default_factory=list)
    clean_sections: list[str] = Field(default_factory=list)
    clean_statement: str
    # True when verdict + bottom_line + top_blockers were produced by an
    # LLM synthesis pass; False when the rule-based fallback was used.
    synthesized_by_llm: bool = False


class MetaReviewRunRead(BaseModel):
    id: int
    tenant_id: str
    document_version_id: int
    review_job_id: int | None
    input_hash: str
    status: MetaReviewStatus
    queued_at: datetime | None = None
    running_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    is_synthesized: bool
    provider: str
    model: str
    error_code: str | None = None
    error_message: str | None
    error_details: MetaReviewErrorDetailRead | None = None
    created_at: datetime
    comments: list[MetaCommentRead]
    summary: MetaReviewSummaryRead | None = None

    model_config = ConfigDict(from_attributes=True)


class MetaReviewEnsureRead(MetaReviewRunRead):
    resolution: MetaReviewResolution
