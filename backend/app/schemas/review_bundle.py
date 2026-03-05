from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BundleDocument(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class BundleVersion(BaseModel):
    version_label: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class BundleReviewJob(BaseModel):
    status: str = "completed"
    trigger: str = "import"
    provider: str = "import"
    model: str = "bundle"
    quality_telemetry: dict | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None


class BundlePersona(BaseModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    system_prompt: str = Field(min_length=1, max_length=4000)
    focus_areas: list[str] = Field(default_factory=list)
    tone: str | None = None
    reference_notes: str | None = None
    output_requirements: dict = Field(default_factory=dict)
    examples: list[str] = Field(default_factory=list)
    sort_order: int = 100
    color_theme: str | None = None
    is_active: bool = True


class BundleComment(BaseModel):
    id: int | None = None
    persona_id: int | None = None
    persona_name: str | None = None
    text: str = Field(min_length=1)
    start_offset: int = 0
    end_offset: int = 0
    excerpt: str | None = None
    output_metadata: dict | None = None
    created_at: datetime | None = None


class BundleMetaCommentSource(BaseModel):
    comment_id: int | None = None
    reviewer_name: str
    reviewer_id: int = 0
    original_comment_text: str


class BundleMetaComment(BaseModel):
    content: str
    category: str = "clarity"
    priority: str = "medium"
    impact: str = "medium"
    effort: str = "medium"
    confidence: float = 0.5
    why_now: str | None = None
    recommended_change: str | None = None
    verification_step: str | None = None
    status: str = "open"
    assignee: str | None = None
    due_at: str | None = None
    rank_score: float = 0.0
    start_offset: int = 0
    end_offset: int = 0
    order_index: int = 0
    is_unsynthesized: bool = False
    sources: list[BundleMetaCommentSource] = Field(default_factory=list)


class BundleMetaReviewRun(BaseModel):
    status: str = "completed"
    queued_at: datetime | None = None
    running_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    is_synthesized: bool = True
    provider: str = "import"
    model: str = "bundle"
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    comments: list[BundleMetaComment] = Field(default_factory=list)


class ReviewBundleImport(BaseModel):
    schema_version: str | None = None
    exported_at: datetime | None = None
    document: BundleDocument
    version: BundleVersion
    review_job: BundleReviewJob | None = None
    personas: list[BundlePersona] = Field(default_factory=list)
    comments: list[BundleComment] = Field(default_factory=list)
    meta_review_run: BundleMetaReviewRun | None = None


class ReviewBundleImportResult(BaseModel):
    document_id: int
    version_id: int
    review_job_id: int | None = None
    comments_imported: int
    personas_created: int
    meta_comments_imported: int

    model_config = ConfigDict(from_attributes=True)
