from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)


class DocumentRead(DocumentBase):
    id: int
    tenant_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
