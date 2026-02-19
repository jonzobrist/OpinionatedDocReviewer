from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from redis import Redis
from rq import Queue, Worker
from rq.job import Job
from rq.registry import (
    DeferredJobRegistry,
    FailedJobRegistry,
    FinishedJobRegistry,
    ScheduledJobRegistry,
    StartedJobRegistry,
)
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id, require_admin_user
from app.core.config import settings
from app.db import models
from app.schemas.worker_monitor import (
    WorkerLogEventRead,
    WorkerMonitorRead,
    WorkerQueueStatsRead,
    WorkerSnapshotRead,
)

router = APIRouter(
    prefix="/admin/worker-monitor",
    tags=["admin"],
    dependencies=[Depends(require_admin_user)],
)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _truncate(text: str, limit: int = 350) -> str:
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return f"{stripped[: limit - 1]}…"


@router.get("", response_model=WorkerMonitorRead)
def get_worker_monitor(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> WorkerMonitorRead:
    logs: list[WorkerLogEventRead] = []
    queue_stats = WorkerQueueStatsRead(
        name=settings.REVIEW_QUEUE_NAME,
        queued=0,
        started=0,
        scheduled=0,
        deferred=0,
        failed=0,
        finished=0,
    )
    workers: list[WorkerSnapshotRead] = []
    redis_ok = False
    redis_error: str | None = None

    try:
        redis = Redis.from_url(settings.REDIS_URL)
        redis_ok = bool(redis.ping())
        queue = Queue(settings.REVIEW_QUEUE_NAME, connection=redis)
        queue_stats = WorkerQueueStatsRead(
            name=queue.name,
            queued=int(queue.count),
            started=int(StartedJobRegistry(queue=queue).count),
            scheduled=int(ScheduledJobRegistry(queue=queue).count),
            deferred=int(DeferredJobRegistry(queue=queue).count),
            failed=int(FailedJobRegistry(queue=queue).count),
            finished=int(FinishedJobRegistry(queue=queue).count),
        )

        for worker in Worker.all(connection=redis):
            queues = list(worker.queue_names())
            if queue.name not in queues:
                continue
            workers.append(
                WorkerSnapshotRead(
                    name=worker.name,
                    state=worker.state,
                    queues=queues,
                    current_job_id=worker.get_current_job_id(),
                    last_heartbeat=_as_utc(worker.last_heartbeat),
                )
            )

        failed_ids = FailedJobRegistry(queue=queue).get_job_ids()[:10]
        for rq_job_id in failed_ids:
            try:
                rq_job = Job.fetch(rq_job_id, connection=redis)
            except Exception:
                continue
            event_time = _as_utc(rq_job.ended_at or rq_job.started_at or rq_job.enqueued_at) or datetime.now(
                timezone.utc
            )
            logs.append(
                WorkerLogEventRead(
                    id=f"rq-failed-{rq_job_id}",
                    timestamp=event_time,
                    level="error",
                    source="rq",
                    message=f"RQ job {rq_job_id} failed",
                    detail=_truncate(rq_job.exc_info or "No traceback available"),
                    rq_job_id=rq_job_id,
                )
            )
    except Exception as exc:
        redis_error = str(exc)

    recent_jobs = (
        db.query(models.ReviewJob, models.DocumentVersion, models.Document)
        .join(models.DocumentVersion, models.DocumentVersion.id == models.ReviewJob.document_version_id)
        .join(models.Document, models.Document.id == models.DocumentVersion.document_id)
        .filter(models.ReviewJob.tenant_id == tenant_id)
        .order_by(models.ReviewJob.created_at.desc())
        .limit(40)
        .all()
    )

    for job, _version, document in recent_jobs:
        status = job.status.lower()
        if status == "failed":
            level = "error"
        elif status in {"queued", "running"}:
            level = "warn"
        else:
            level = "info"
        logs.append(
            WorkerLogEventRead(
                id=f"review-job-{job.id}-{job.created_at.timestamp()}",
                timestamp=_as_utc(job.completed_at or job.created_at) or datetime.now(timezone.utc),
                level=level,
                source="review",
                message=f"Review job #{job.id} is {job.status}",
                review_job_id=job.id,
                document_title=document.title,
            )
        )

    logs = sorted(logs, key=lambda item: item.timestamp, reverse=True)[:100]
    return WorkerMonitorRead(
        redis_ok=redis_ok,
        redis_error=redis_error,
        queue=queue_stats,
        workers=workers,
        logs=logs,
    )

