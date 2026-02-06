from app.reviews.queue import enqueue_review_job


def test_enqueue_review_job_calls_queue(monkeypatch) -> None:
    calls = {}

    class DummyQueue:
        def __init__(self, *args, **kwargs):
            pass

        def enqueue(self, *args, **kwargs):
            calls["args"] = args
            calls["kwargs"] = kwargs

    monkeypatch.setattr("app.reviews.queue.Queue", DummyQueue)

    enqueue_review_job(7, "tenant-x")

    assert "args" in calls
    assert calls["kwargs"]["review_job_id"] == 7
    assert calls["kwargs"]["tenant_id"] == "tenant-x"
