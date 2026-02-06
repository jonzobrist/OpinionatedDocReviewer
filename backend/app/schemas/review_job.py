from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ReviewJobCreate(BaseModel):
    document_version_id: int


class ReviewJobRead(BaseModel):
    id: int
    tenant_id: str
    document_version_id: int
    status: str = Field(min_length=1, max_length=50)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
