from __future__ import annotations

from datetime import datetime, timezone


def _create_review_job(client, tenant: str = "tenant-monitor") -> int:
    headers = {"X-Tenant-Id": tenant}
    doc_resp = client.post("/api/documents", json={"title": "Queue doc"}, headers=headers)
    doc_id = doc_resp.json()["id"]
    version_resp = client.post(
        f"/api/documents/{doc_id}/versions",
        json={"version_label": "v1", "content": "hello queue"},
        headers=headers,
    )
    version_id = version_resp.json()["id"]
    job_resp = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_id},
        headers=headers,
    )
    return job_resp.json()["id"]


def test_worker_monitor_returns_review_events_when_redis_unavailable(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.review_jobs.enqueue_review_job", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.api.worker_monitor.Redis.from_url",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("redis offline")),
    )
    job_id = _create_review_job(client)

    resp = client.get("/api/admin/worker-monitor", headers={"X-Tenant-Id": "tenant-monitor"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["redis_ok"] is False
    assert "redis offline" in (payload["redis_error"] or "")
    assert payload["queue"]["queued"] == 0
    assert any(event.get("review_job_id") == job_id for event in payload["logs"])


def test_worker_monitor_includes_queue_stats_worker_and_rq_failure_logs(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.review_jobs.enqueue_review_job", lambda *_args, **_kwargs: None)
    _create_review_job(client, tenant="tenant-monitor-rq")

    class DummyRedis:
        def ping(self) -> bool:
            return True

    class DummyQueue:
        def __init__(self, name: str, connection) -> None:
            self.name = name
            self.connection = connection
            self.count = 4

    class DummyWorker:
        name = "worker-a"
        state = "busy"
        last_heartbeat = datetime(2026, 2, 19, 5, 0, tzinfo=timezone.utc)

        def queue_names(self) -> list[str]:
            return ["review-jobs"]

        def get_current_job_id(self) -> str:
            return "rq-777"

        @classmethod
        def all(cls, connection) -> list["DummyWorker"]:
            return [cls()]

    class _Registry:
        def __init__(self, _count: int, ids: list[str] | None = None) -> None:
            self.count = _count
            self._ids = ids or []

        def get_job_ids(self) -> list[str]:
            return self._ids

    class DummyJob:
        ended_at = datetime(2026, 2, 19, 5, 1, tzinfo=timezone.utc)
        started_at = None
        enqueued_at = None
        exc_info = "Traceback: boom"

        @classmethod
        def fetch(cls, _job_id: str, connection):
            return cls()

    monkeypatch.setattr("app.api.worker_monitor.Redis.from_url", lambda *_args, **_kwargs: DummyRedis())
    monkeypatch.setattr("app.api.worker_monitor.Queue", DummyQueue)
    monkeypatch.setattr("app.api.worker_monitor.Worker", DummyWorker)
    monkeypatch.setattr(
        "app.api.worker_monitor.StartedJobRegistry",
        lambda queue: _Registry(2),
    )
    monkeypatch.setattr(
        "app.api.worker_monitor.ScheduledJobRegistry",
        lambda queue: _Registry(3),
    )
    monkeypatch.setattr(
        "app.api.worker_monitor.DeferredJobRegistry",
        lambda queue: _Registry(1),
    )
    monkeypatch.setattr(
        "app.api.worker_monitor.FinishedJobRegistry",
        lambda queue: _Registry(9),
    )
    monkeypatch.setattr(
        "app.api.worker_monitor.FailedJobRegistry",
        lambda queue: _Registry(5, ids=["rq-err-1"]),
    )
    monkeypatch.setattr("app.api.worker_monitor.Job", DummyJob)

    resp = client.get("/api/admin/worker-monitor", headers={"X-Tenant-Id": "tenant-monitor-rq"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["redis_ok"] is True
    assert payload["queue"]["queued"] == 4
    assert payload["queue"]["failed"] == 5
    assert payload["workers"][0]["name"] == "worker-a"
    assert any(event["rq_job_id"] == "rq-err-1" for event in payload["logs"])

