import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.db import models
from app.db.init_db import seed_default_personas
from app.db.session import SessionLocal
from app.reviews.worker import (
    _auto_trigger_meta_synthesis,
    _generate_with_timeout_retry,
    run_review_job,
)


def _seed_review_context(db, tenant_id: str) -> tuple[models.DocumentVersion, models.ReviewJob]:
    seed_default_personas(tenant_id=tenant_id, db=db)

    doc = models.Document(tenant_id=tenant_id, title="Test Doc")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    version = models.DocumentVersion(
        tenant_id=tenant_id,
        document_id=doc.id,
        version_label="v1",
        content="Hello world.\nThis is a test document.",
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    job = models.ReviewJob(
        tenant_id=tenant_id,
        document_version_id=version.id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return version, job


def test_review_worker_generates_comments_and_auto_triggers_meta(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-auto-trigger"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", True)

        version, job = _seed_review_context(db, tenant_id)

        def _fake_generate_comments_for_spec(persona, content):
            return ['Review: clarify "world" term.']

        trigger_calls: dict[str, int] = {"count": 0}

        def _fake_ensure_meta_review_run(
            *,
            db,
            tenant_id,
            document_version_id,
            review_job_id,
            force,
        ):
            trigger_calls["count"] += 1
            trigger_calls["document_version_id"] = document_version_id
            trigger_calls["review_job_id"] = review_job_id
            trigger_calls["force"] = int(force)
            return SimpleNamespace(
                run=SimpleNamespace(id=777, status="completed"),
                resolution="created",
            )

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            _fake_generate_comments_for_spec,
        )
        monkeypatch.setattr(
            "app.reviews.worker.ensure_meta_review_run",
            _fake_ensure_meta_review_run,
        )

        run_review_job(job.id, tenant_id)

        comments = (
            db.query(models.Comment)
            .filter(models.Comment.document_version_id == version.id)
            .all()
        )
        assert len(comments) > 0
        assert comments[0].excerpt in ("world", None)
        assert comments[0].review_job_id == job.id

        db.refresh(job)
        assert job.status == "completed"
        assert trigger_calls["count"] == 1
        assert trigger_calls["document_version_id"] == version.id
        assert trigger_calls["review_job_id"] == job.id
        assert trigger_calls["force"] == 0
    finally:
        db.close()


def test_review_worker_keeps_completed_status_when_meta_auto_trigger_fails(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-auto-trigger-failure"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", True)
        version, job = _seed_review_context(db, tenant_id)

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            lambda _persona, _content: ['Review: clarify "world" term.'],
        )

        def _raise_meta_error(**_kwargs):
            raise RuntimeError("meta synthesis downstream unavailable")

        monkeypatch.setattr("app.reviews.worker.ensure_meta_review_run", _raise_meta_error)

        run_review_job(job.id, tenant_id)

        db.refresh(job)
        assert job.status == "completed"

        comments = (
            db.query(models.Comment)
            .filter(models.Comment.document_version_id == version.id)
            .all()
        )
        assert len(comments) > 0

        runs = (
            db.query(models.MetaReviewRun)
            .filter(
                models.MetaReviewRun.tenant_id == tenant_id,
                models.MetaReviewRun.document_version_id == version.id,
                models.MetaReviewRun.review_job_id == job.id,
            )
            .all()
        )
        assert runs == []
    finally:
        db.close()


def test_review_worker_skips_meta_auto_trigger_when_disabled(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-auto-disabled"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", False)
        version, job = _seed_review_context(db, tenant_id)

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            lambda _persona, _content: ['Review: clarify "world" term.'],
        )

        def _should_not_be_called(**_kwargs):
            raise AssertionError("ensure_meta_review_run should not be called when auto trigger is disabled")

        monkeypatch.setattr("app.reviews.worker.ensure_meta_review_run", _should_not_be_called)

        run_review_job(job.id, tenant_id)

        db.refresh(job)
        assert job.status == "completed"

        runs = (
            db.query(models.MetaReviewRun)
            .filter(
                models.MetaReviewRun.tenant_id == tenant_id,
                models.MetaReviewRun.document_version_id == version.id,
                models.MetaReviewRun.review_job_id == job.id,
            )
            .all()
        )
        assert runs == []
    finally:
        db.close()


def test_meta_auto_trigger_is_idempotent_for_duplicate_completion_events(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-meta-idempotent"
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", True)

        seed_default_personas(tenant_id=tenant_id, db=db)
        personas = (
            db.query(models.Persona)
            .filter(models.Persona.tenant_id == tenant_id, models.Persona.is_active.is_(True))
            .order_by(models.Persona.id.asc())
            .all()
        )
        assert len(personas) >= 2

        doc = models.Document(tenant_id=tenant_id, title="Doc")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        version = models.DocumentVersion(
            tenant_id=tenant_id,
            document_id=doc.id,
            version_label="v1",
            content="alpha beta gamma delta epsilon",
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        job = models.ReviewJob(
            tenant_id=tenant_id,
            document_version_id=version.id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        db.add(
            models.Comment(
                tenant_id=tenant_id,
                document_version_id=version.id,
                review_job_id=job.id,
                persona_id=personas[0].id,
                text="Clarify intro sentence.",
                start_offset=0,
                end_offset=10,
                excerpt="alpha beta",
                output_metadata={},
            )
        )
        db.add(
            models.Comment(
                tenant_id=tenant_id,
                document_version_id=version.id,
                review_job_id=job.id,
                persona_id=personas[1].id,
                text="Security: token handling is vague.",
                start_offset=8,
                end_offset=24,
                excerpt="beta gamma delta",
                output_metadata={},
            )
        )
        db.commit()

        synth_calls = {"count": 0}

        def _fake_generate(_prompt: str) -> str:
            synth_calls["count"] += 1
            return json.dumps(
                [
                    {
                        "content": "Specify token validation and expiration rules.",
                        "category": "security",
                        "priority": "high",
                        "impact": "high",
                        "effort": "medium",
                        "confidence": 0.9,
                        "why_now": "Ambiguity can lead to insecure implementation.",
                        "recommended_change": "Add explicit token checks and expiry behavior.",
                        "verification_step": "Re-run review and confirm no unresolved security directives.",
                        "status": "open",
                        "assignee": None,
                        "due_at": None,
                        "contributing_reviewers": [personas[0].name, personas[1].name],
                        "location": {"start_offset": 0, "end_offset": 24},
                    }
                ]
            )

        monkeypatch.setattr("app.reviews.meta_reviewer.generate_completion", _fake_generate)

        _auto_trigger_meta_synthesis(
            db=db,
            tenant_id=tenant_id,
            review_job_id=job.id,
            document_version_id=version.id,
        )
        _auto_trigger_meta_synthesis(
            db=db,
            tenant_id=tenant_id,
            review_job_id=job.id,
            document_version_id=version.id,
        )

        runs = (
            db.query(models.MetaReviewRun)
            .filter(
                models.MetaReviewRun.tenant_id == tenant_id,
                models.MetaReviewRun.document_version_id == version.id,
                models.MetaReviewRun.review_job_id == job.id,
            )
            .all()
        )
        assert len(runs) == 1
        assert synth_calls["count"] == 1
    finally:
        db.close()


def test_generate_with_timeout_retry_retries_on_timeout(monkeypatch) -> None:
    calls = {"count": 0}

    def _fake_generate(_prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise TimeoutError("request timed out")
        return "- \"a\" :: ok"

    monkeypatch.setattr("app.reviews.worker.generate_completion", _fake_generate)
    monkeypatch.setattr("app.reviews.worker.time.sleep", lambda _seconds: None)
    output = _generate_with_timeout_retry("prompt")
    assert output == '- "a" :: ok'
    assert calls["count"] == 3
