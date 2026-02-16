from __future__ import annotations

from pydantic import BaseModel, Field


class SystemConfigRead(BaseModel):
    llm_provider: str
    openai_model: str
    openai_max_tokens: int
    openai_temperature: float
    openai_timeout_seconds: int
    bedrock_model_id: str
    bedrock_region: str
    review_inline: bool
    redis_url: str
    review_queue_name: str
    doc_repo_enabled: bool
    doc_repo_root: str
    cors_allow_origins: str
    cors_allow_origin_regex: str | None = None
    cors_allow_credentials: bool
    cors_allow_methods: str
    cors_allow_headers: str
    cors_max_age: int
    openai_api_key_set: bool
    bedrock_access_key_set: bool
    bedrock_secret_key_set: bool
    bedrock_session_token_set: bool


class SystemConfigUpdate(BaseModel):
    llm_provider: str = Field(pattern="^(openai|bedrock)$")
    openai_model: str
    openai_max_tokens: int = Field(ge=1, le=8192)
    openai_temperature: float = Field(ge=0.0, le=2.0)
    openai_timeout_seconds: int = Field(ge=1, le=120)
    bedrock_model_id: str
    bedrock_region: str
    review_inline: bool
    redis_url: str
    review_queue_name: str
    doc_repo_enabled: bool
    doc_repo_root: str
    cors_allow_origins: str
    cors_allow_origin_regex: str | None = None
    cors_allow_credentials: bool
    cors_allow_methods: str
    cors_allow_headers: str
    cors_max_age: int = Field(ge=0, le=86400)
    openai_api_key: str | None = None
    bedrock_aws_access_key_id: str | None = None
    bedrock_aws_secret_access_key: str | None = None
    bedrock_aws_session_token: str | None = None
