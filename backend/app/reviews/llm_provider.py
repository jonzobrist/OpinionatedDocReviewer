from __future__ import annotations

from typing import Any

from openai import OpenAIError

from app.core.config import settings
from app.reviews.openai_client import get_openai_client


class LLMProviderError(RuntimeError):
    pass


def get_provider_name() -> str:
    return settings.LLM_PROVIDER.strip().lower()


def get_model_label() -> str:
    provider = get_provider_name()
    if provider == "bedrock":
        return settings.BEDROCK_MODEL_ID
    if provider == "llamacpp":
        return settings.LLAMACPP_MODEL
    return settings.OPENAI_MODEL


def generate_completion(prompt: str) -> str:
    provider = get_provider_name()
    if provider == "openai":
        return _generate_with_openai(prompt)
    if provider == "bedrock":
        return _generate_with_bedrock(prompt)
    if provider == "llamacpp":
        return _generate_with_llamacpp(prompt)
    raise LLMProviderError(f"Unsupported LLM provider: {settings.LLM_PROVIDER}")


def provider_health() -> dict[str, Any]:
    provider = get_provider_name()
    if provider == "llamacpp":
        try:
            import httpx
            resp = httpx.get(f"{settings.LLAMACPP_BASE_URL}/models", timeout=5)
            ok = resp.status_code == 200
            return {"provider": "llamacpp", "ok": ok, "error": None if ok else f"HTTP {resp.status_code}", "model": settings.LLAMACPP_MODEL}
        except Exception as exc:
            return {"provider": "llamacpp", "ok": False, "error": str(exc), "model": settings.LLAMACPP_MODEL}
    if provider == "openai":
        return {
            "provider": "openai",
            "ok": bool(settings.OPENAI_API_KEY),
            "error": None if settings.OPENAI_API_KEY else "OPENAI_API_KEY is not set",
            "model": settings.OPENAI_MODEL,
        }
    if provider == "bedrock":
        try:
            import boto3

            session = _build_bedrock_session(boto3)
            credentials = session.get_credentials()
            if not settings.BEDROCK_MODEL_ID:
                return {
                    "provider": "bedrock",
                    "ok": False,
                    "error": "BEDROCK_MODEL_ID is not set",
                    "model": settings.BEDROCK_MODEL_ID,
                }
            if credentials is None:
                return {
                    "provider": "bedrock",
                    "ok": False,
                    "error": "AWS credentials not found for Bedrock",
                    "model": settings.BEDROCK_MODEL_ID,
                }
            return {
                "provider": "bedrock",
                "ok": True,
                "error": None,
                "model": settings.BEDROCK_MODEL_ID,
            }
        except Exception as exc:
            return {
                "provider": "bedrock",
                "ok": False,
                "error": str(exc),
                "model": settings.BEDROCK_MODEL_ID,
            }
    return {
        "provider": provider,
        "ok": False,
        "error": f"Unsupported LLM provider: {settings.LLM_PROVIDER}",
        "model": None,
    }


def _generate_with_llamacpp(prompt: str) -> str:
    from openai import OpenAI as _OpenAI, OpenAIError
    client = _OpenAI(
        base_url=settings.LLAMACPP_BASE_URL,
        api_key=settings.LLAMACPP_API_KEY,
        timeout=settings.OPENAI_TIMEOUT_SECONDS,
    )
    try:
        response = client.chat.completions.create(
            model=settings.LLAMACPP_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.LLAMACPP_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise LLMProviderError("llamacpp returned no text output")
        return text
    except OpenAIError as exc:
        raise LLMProviderError(str(exc)) from exc


def _generate_with_openai(prompt: str) -> str:
    client = get_openai_client()
    try:
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=prompt,
            max_output_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE,
        )
        return response.output_text
    except OpenAIError as exc:
        raise LLMProviderError(str(exc)) from exc


def _build_bedrock_session(boto3_module):
    kwargs: dict[str, str] = {}
    if settings.BEDROCK_REGION:
        kwargs["region_name"] = settings.BEDROCK_REGION
    if settings.BEDROCK_AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.BEDROCK_AWS_ACCESS_KEY_ID
    if settings.BEDROCK_AWS_SECRET_ACCESS_KEY:
        kwargs["aws_secret_access_key"] = settings.BEDROCK_AWS_SECRET_ACCESS_KEY
    if settings.BEDROCK_AWS_SESSION_TOKEN:
        kwargs["aws_session_token"] = settings.BEDROCK_AWS_SESSION_TOKEN
    return boto3_module.Session(**kwargs)


def _generate_with_bedrock(prompt: str) -> str:
    try:
        import boto3
        from botocore.config import Config as BotoConfig
    except Exception as exc:
        raise LLMProviderError(f"boto3 is required for Bedrock: {exc}") from exc

    session = _build_bedrock_session(boto3)
    client = session.client(
        "bedrock-runtime",
        config=BotoConfig(
            connect_timeout=settings.OPENAI_TIMEOUT_SECONDS,
            read_timeout=settings.OPENAI_TIMEOUT_SECONDS,
        ),
    )
    try:
        response = client.converse(
            modelId=settings.BEDROCK_MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": prompt,
                        }
                    ],
                }
            ],
            inferenceConfig={
                "maxTokens": settings.OPENAI_MAX_TOKENS,
                "temperature": settings.OPENAI_TEMPERATURE,
            },
        )
    except Exception as exc:
        raise LLMProviderError(str(exc)) from exc

    message = (response.get("output") or {}).get("message") or {}
    content = message.get("content") or []
    text_chunks = [item.get("text", "") for item in content if isinstance(item, dict)]
    text = "\n".join(chunk for chunk in text_chunks if chunk).strip()
    if not text:
        raise LLMProviderError("Bedrock returned no text output")
    return text
