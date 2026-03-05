from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.reviews.quality_telemetry import build_empty_review_quality_telemetry


class ReviewJobCreate(BaseModel):
    document_version_id: int
    trigger: str | None = None


class ReviewJobQualityPersonaRead(BaseModel):
    persona_id: int | None = None
    total_comments: int = Field(default=0, ge=0)
    fallback_count: int = Field(default=0, ge=0)
    truncated_count: int = Field(default=0, ge=0)
    violation_count_by_type: dict[str, int] = Field(default_factory=dict)


class ReviewJobQualitySummaryRead(BaseModel):
    total_comments: int = Field(default=0, ge=0)
    fallback_count: int = Field(default=0, ge=0)
    truncated_count: int = Field(default=0, ge=0)
    violation_count_by_type: dict[str, int] = Field(default_factory=dict)
    per_persona: dict[str, ReviewJobQualityPersonaRead] = Field(default_factory=dict)


class ReviewJobRead(BaseModel):
    id: int
    tenant_id: str
    document_version_id: int
    status: str = Field(min_length=1, max_length=50)
    trigger: str
    provider: str
    model: str
    generation_index: int | None = Field(default=None, ge=1)
    is_latest_for_version: bool | None = None
    comment_count: int = Field(default=0, ge=0)
    quality_telemetry: ReviewJobQualitySummaryRead = Field(
        default_factory=lambda: ReviewJobQualitySummaryRead(**build_empty_review_quality_telemetry())
    )
    completed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
