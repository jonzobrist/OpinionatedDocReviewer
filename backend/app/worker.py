import os

from redis import Redis
from rq import SimpleWorker

from app.core.config import settings


def main() -> None:
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
    redis = Redis.from_url(settings.REDIS_URL)
    worker = SimpleWorker([settings.REVIEW_QUEUE_NAME], connection=redis)
    worker.work(with_scheduler=True, logging_level="INFO")


if __name__ == "__main__":
    main()
