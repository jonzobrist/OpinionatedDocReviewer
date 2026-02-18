from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from app.core.config import settings


class CommentBase(BaseModel):
    persona_id: int
    document_version_id: int
    review_job_id: int | None = None
    text: str = Field(min_length=1, max_length=settings.COMMENT_MAX_CHARS)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    excerpt: str | None = Field(default=None, max_length=1000)
    output_metadata: dict | None = None


class CommentCreate(CommentBase):
    pass


class CommentRead(CommentBase):
    id: int
    tenant_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
