from openai import OpenAI

from app.core.config import settings


def get_openai_client() -> OpenAI:
    if settings.OPENAI_API_KEY:
        return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS)
    return OpenAI(timeout=settings.OPENAI_TIMEOUT_SECONDS)
