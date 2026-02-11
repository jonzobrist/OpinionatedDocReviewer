from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentBase(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)


class DocumentArchiveUpdate(BaseModel):
    archived: bool


class DocumentRead(DocumentBase):
    id: int
    tenant_id: str
    is_archived: bool
    archived_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentLibraryEntry(BaseModel):
    id: int
    tenant_id: str
    title: str
    is_archived: bool
    archived_at: datetime | None
    created_at: datetime
    latest_version_id: int | None
    latest_version_label: str | None
    latest_version_created_at: datetime | None
    latest_review_job_id: int | None
    latest_review_status: str | None
    latest_review_created_at: datetime | None
    latest_review_completed_at: datetime | None
    needs_review: bool

    model_config = ConfigDict(from_attributes=True)
