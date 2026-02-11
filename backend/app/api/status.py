from __future__ import annotations

from fastapi import APIRouter
from redis import Redis

from app.core.config import settings
from app.reviews.llm_provider import provider_health

router = APIRouter(prefix="/status", tags=["status"])


@router.get("")
def status() -> dict:
    redis_ok = False
    redis_error: str | None = None
    try:
        redis = Redis.from_url(settings.REDIS_URL)
        redis_ok = bool(redis.ping())
    except Exception as exc:
        redis_error = str(exc)

    llm = provider_health()
    openai_ok = bool(settings.OPENAI_API_KEY)

    return {
        "redis": {"ok": redis_ok, "error": redis_error},
        "llm": llm,
        "openai": {"ok": openai_ok},
        "review_queue": settings.REVIEW_QUEUE_NAME,
        "doc_repo_enabled": settings.DOC_REPO_ENABLED,
    }
