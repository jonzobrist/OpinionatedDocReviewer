from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_tenant_id
from app.core.config import save_config_values, settings
from app.schemas.settings import SystemConfigRead, SystemConfigUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


def _bool_set(value: str | None) -> bool:
    return bool(value and value.strip())


def _read_settings() -> SystemConfigRead:
    return SystemConfigRead(
        llm_provider=settings.LLM_PROVIDER,
        openai_model=settings.OPENAI_MODEL,
        openai_max_tokens=settings.OPENAI_MAX_TOKENS,
        openai_temperature=settings.OPENAI_TEMPERATURE,
        openai_timeout_seconds=settings.OPENAI_TIMEOUT_SECONDS,
        bedrock_model_id=settings.BEDROCK_MODEL_ID,
        bedrock_region=settings.BEDROCK_REGION,
        review_inline=settings.REVIEW_INLINE,
        openai_api_key_set=_bool_set(settings.OPENAI_API_KEY),
        bedrock_access_key_set=_bool_set(settings.BEDROCK_AWS_ACCESS_KEY_ID),
        bedrock_secret_key_set=_bool_set(settings.BEDROCK_AWS_SECRET_ACCESS_KEY),
        bedrock_session_token_set=_bool_set(settings.BEDROCK_AWS_SESSION_TOKEN),
    )


@router.get("", response_model=SystemConfigRead)
def get_settings(_: str = Depends(get_tenant_id)) -> SystemConfigRead:
    return _read_settings()


@router.put("", response_model=SystemConfigRead)
def update_settings(payload: SystemConfigUpdate, _: str = Depends(get_tenant_id)) -> SystemConfigRead:
    settings.LLM_PROVIDER = payload.llm_provider
    settings.OPENAI_MODEL = payload.openai_model
    settings.OPENAI_MAX_TOKENS = payload.openai_max_tokens
    settings.OPENAI_TEMPERATURE = payload.openai_temperature
    settings.OPENAI_TIMEOUT_SECONDS = payload.openai_timeout_seconds
    settings.BEDROCK_MODEL_ID = payload.bedrock_model_id
    settings.BEDROCK_REGION = payload.bedrock_region
    settings.REVIEW_INLINE = payload.review_inline

    updates: dict[str, str | int | float | bool] = {
        "LLM_PROVIDER": settings.LLM_PROVIDER,
        "OPENAI_MODEL": settings.OPENAI_MODEL,
        "OPENAI_MAX_TOKENS": settings.OPENAI_MAX_TOKENS,
        "OPENAI_TEMPERATURE": settings.OPENAI_TEMPERATURE,
        "OPENAI_TIMEOUT_SECONDS": settings.OPENAI_TIMEOUT_SECONDS,
        "BEDROCK_MODEL_ID": settings.BEDROCK_MODEL_ID,
        "BEDROCK_REGION": settings.BEDROCK_REGION,
        "REVIEW_INLINE": settings.REVIEW_INLINE,
    }

    if payload.openai_api_key is not None:
        settings.OPENAI_API_KEY = payload.openai_api_key.strip() or None
        updates["OPENAI_API_KEY"] = settings.OPENAI_API_KEY or ""

    if payload.bedrock_aws_access_key_id is not None:
        settings.BEDROCK_AWS_ACCESS_KEY_ID = payload.bedrock_aws_access_key_id.strip() or None
        updates["BEDROCK_AWS_ACCESS_KEY_ID"] = settings.BEDROCK_AWS_ACCESS_KEY_ID or ""

    if payload.bedrock_aws_secret_access_key is not None:
        settings.BEDROCK_AWS_SECRET_ACCESS_KEY = (
            payload.bedrock_aws_secret_access_key.strip() or None
        )
        updates["BEDROCK_AWS_SECRET_ACCESS_KEY"] = settings.BEDROCK_AWS_SECRET_ACCESS_KEY or ""

    if payload.bedrock_aws_session_token is not None:
        settings.BEDROCK_AWS_SESSION_TOKEN = payload.bedrock_aws_session_token.strip() or None
        updates["BEDROCK_AWS_SESSION_TOKEN"] = settings.BEDROCK_AWS_SESSION_TOKEN or ""

    save_config_values(updates)
    return _read_settings()
