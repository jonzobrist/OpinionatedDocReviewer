from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WorkerSnapshotRead(BaseModel):
    name: str
    state: str
    queues: list[str]
    current_job_id: str | None = None
    last_heartbeat: datetime | None = None


class WorkerQueueStatsRead(BaseModel):
    name: str
    queued: int
    started: int
    scheduled: int
    deferred: int
    failed: int
    finished: int


class WorkerLogEventRead(BaseModel):
    id: str
    timestamp: datetime
    level: str
    source: str
    message: str
    detail: str | None = None
    review_job_id: int | None = None
    rq_job_id: str | None = None
    document_title: str | None = None


class WorkerMonitorRead(BaseModel):
    redis_ok: bool
    redis_error: str | None = None
    queue: WorkerQueueStatsRead
    workers: list[WorkerSnapshotRead]
    logs: list[WorkerLogEventRead]

