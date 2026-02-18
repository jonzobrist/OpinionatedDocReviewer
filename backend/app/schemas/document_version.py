from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from app.core.config import settings


class DocumentVersionBase(BaseModel):
    version_label: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=settings.DOC_MAX_CHARS)


class DocumentVersionCreate(DocumentVersionBase):
    pass


class DocumentVersionRead(DocumentVersionBase):
    id: int
    tenant_id: str
    document_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
