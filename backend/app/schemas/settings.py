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
    meta_agent_name: str
    meta_agent_description: str
    meta_agent_system_prompt: str
    meta_agent_focus_areas: str
    meta_agent_tone: str
    meta_agent_reference_notes: str | None = None
    meta_agent_output_format: str
    meta_agent_output_max_bullets: int
    meta_agent_output_require_quote_excerpt: bool
    meta_agent_output_require_actionable: bool
    meta_agent_output_include_severity: bool
    meta_agent_examples: str
    meta_max_directives_per_group: int
    meta_global_dedupe_threshold: float
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
    meta_agent_name: str = Field(min_length=1, max_length=200)
    meta_agent_description: str = Field(max_length=1000)
    meta_agent_system_prompt: str = Field(min_length=1, max_length=4000)
    meta_agent_focus_areas: str
    meta_agent_tone: str = Field(max_length=200)
    meta_agent_reference_notes: str | None = None
    meta_agent_output_format: str = Field(max_length=100)
    meta_agent_output_max_bullets: int = Field(ge=1, le=20)
    meta_agent_output_require_quote_excerpt: bool
    meta_agent_output_require_actionable: bool
    meta_agent_output_include_severity: bool
    meta_agent_examples: str
    meta_max_directives_per_group: int = Field(ge=1, le=20)
    meta_global_dedupe_threshold: float = Field(ge=0.0, le=1.0)
    openai_api_key: str | None = None
    bedrock_aws_access_key_id: str | None = None
    bedrock_aws_secret_access_key: str | None = None
    bedrock_aws_session_token: str | None = None
