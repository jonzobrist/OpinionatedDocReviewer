from redis import Redis
from rq import Queue, Retry

from app.core.config import settings


def get_redis_connection() -> Redis:
    return Redis.from_url(settings.REDIS_URL)


def enqueue_review_job(job_id: int, tenant_id: str) -> None:
    redis = get_redis_connection()
    queue = Queue(settings.REVIEW_QUEUE_NAME, connection=redis)
    queue.enqueue(
        "app.reviews.worker.run_review_job",
        review_job_id=job_id,
        tenant_id=tenant_id,
        retry=Retry(max=3, interval=[10, 30, 60]),
        job_timeout=settings.REVIEW_JOB_TIMEOUT_SECONDS,
        result_ttl=0,
    )
