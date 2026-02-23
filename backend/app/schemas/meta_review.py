from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MetaReviewCreate(BaseModel):
    document_version_id: int = Field(gt=0)
    review_job_id: int | None = Field(default=None, gt=0)
    force: bool = False


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


class MetaReviewRunRead(BaseModel):
    id: int
    tenant_id: str
    document_version_id: int
    review_job_id: int | None
    input_hash: str
    status: str
    is_synthesized: bool
    provider: str
    model: str
    error_message: str | None
    created_at: datetime
    comments: list[MetaCommentRead]

    model_config = ConfigDict(from_attributes=True)
