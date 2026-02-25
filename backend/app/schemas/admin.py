from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(
        pattern="^(reader|reviewer|author|project_admin|system_admin|auditor|service_account|admin|default)$"
    )
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    role: str | None = Field(
        default=None,
        pattern="^(reader|reviewer|author|project_admin|system_admin|auditor|service_account|admin|default)$",
    )
    tags: list[str] | None = None
    is_active: bool | None = None


class AdminUserRead(BaseModel):
    id: int
    tenant_id: str
    name: str
    email: str
    role: str
    tags: list[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentPermissionCreate(BaseModel):
    document_id: int
    user_id: int
    permission_level: str = Field(pattern="^(owner|editor|viewer)$")


class DocumentPermissionUpdate(BaseModel):
    permission_level: str = Field(pattern="^(owner|editor|viewer)$")


class DocumentPermissionRead(BaseModel):
    id: int
    tenant_id: str
    document_id: int
    user_id: int
    permission_level: str
    created_at: datetime
    user_name: str
    user_email: str


class AdminJobRead(BaseModel):
    id: int
    document_version_id: int
    document_id: int
    document_title: str
    status: str
    trigger: str
    provider: str
    model: str
    created_at: datetime
    completed_at: datetime | None


class AdminActionRead(BaseModel):
    id: int
    actor_user_id: int | None
    actor_email: str | None
    action: str
    target_type: str
    target_id: int | None
    details: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminOverview(BaseModel):
    tenant_id: str
    repository: dict
    users: dict
    documents: dict
    jobs: dict
    in_progress_jobs: list[AdminJobRead]
    recent_jobs: list[AdminJobRead]
    recent_actions: list[AdminActionRead]


class ResourcePolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    effect: str = Field(pattern="^(allow|deny)$")
    action: str = Field(min_length=1, max_length=64)
    resource_type: str = Field(default="document", min_length=1, max_length=64)
    resource_id: int | None = None
    conditions: dict = Field(default_factory=dict)
    is_active: bool = True


class ResourcePolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    effect: str | None = Field(default=None, pattern="^(allow|deny)$")
    action: str | None = Field(default=None, min_length=1, max_length=64)
    resource_type: str | None = Field(default=None, min_length=1, max_length=64)
    resource_id: int | None = None
    conditions: dict | None = None
    is_active: bool | None = None


class ResourcePolicyRead(BaseModel):
    id: int
    tenant_id: str
    name: str
    effect: str
    action: str
    resource_type: str
    resource_id: int | None
    conditions: dict
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PolicyDecisionLogRead(BaseModel):
    id: int
    tenant_id: str
    user_id: int
    document_id: int | None
    action: str
    requested_level: str
    base_level: str | None
    final_level: str | None
    outcome: str
    matched_policy_ids: list[int]
    details: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
