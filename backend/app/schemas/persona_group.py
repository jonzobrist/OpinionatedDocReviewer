from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PersonaGroupBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class PersonaGroupCreate(PersonaGroupBase):
    pass


class PersonaGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class PersonaGroupRead(PersonaGroupBase):
    id: int
    tenant_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
