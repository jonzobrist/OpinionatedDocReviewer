from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CommentBase(BaseModel):
    persona_id: int
    document_version_id: int
    text: str = Field(min_length=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    excerpt: str | None = None


class CommentCreate(CommentBase):
    pass


class CommentRead(CommentBase):
    id: int
    tenant_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
