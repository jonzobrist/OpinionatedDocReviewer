from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class PersonaBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    system_prompt: str = Field(min_length=1, max_length=4000)
    focus_areas: List[str] = Field(default_factory=list)
    tone: str | None = Field(default=None, max_length=200)
    group_id: int | None = None
    is_active: bool = True


class PersonaCreate(PersonaBase):
    pass


class PersonaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=4000)
    focus_areas: List[str] | None = None
    tone: str | None = Field(default=None, max_length=200)
    group_id: int | None = None
    is_active: bool | None = None


class PersonaRead(PersonaBase):
    id: int
    tenant_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
