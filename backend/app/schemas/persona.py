from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class PersonaOutputRequirements(BaseModel):
    format: str = Field(default="bullet_list", max_length=100)
    max_bullets: int = Field(default=4, ge=1, le=20)
    require_quote_excerpt: bool = True
    require_actionable: bool = True
    include_severity: bool = False


class PersonaBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    system_prompt: str = Field(min_length=1, max_length=4000)
    focus_areas: List[str] = Field(default_factory=list)
    tone: str | None = Field(default=None, max_length=200)
    reference_notes: str | None = Field(default=None, max_length=12000)
    output_requirements: PersonaOutputRequirements = Field(
        default_factory=PersonaOutputRequirements
    )
    examples: List[str] = Field(default_factory=list)
    is_default: bool = False
    is_system_locked: bool = False
    sort_order: int = Field(default=100, ge=0, le=100000)
    color_theme: str | None = Field(default=None, max_length=32)
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
    reference_notes: str | None = Field(default=None, max_length=12000)
    output_requirements: PersonaOutputRequirements | None = None
    examples: List[str] | None = None
    is_default: bool | None = None
    is_system_locked: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    color_theme: str | None = Field(default=None, max_length=32)
    group_id: int | None = None
    is_active: bool | None = None


class PersonaRead(PersonaBase):
    id: int
    tenant_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
