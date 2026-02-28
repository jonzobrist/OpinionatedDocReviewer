from uuid import uuid4

from app.db import models
from app.db.init_db import seed_default_personas
from app.db.session import SessionLocal
from app.reviews.worker import run_review_job, _generate_with_timeout_retry


def test_review_worker_generates_comments(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
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

        def _fake_generate_comments_for_spec(persona, content):
            return ['Review: clarify "world" term.']

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            _fake_generate_comments_for_spec,
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


def test_custom_agent_review_output_metadata_reflects_output_requirements(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = f"tenant-e2e-agent-{uuid4().hex}"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)

        persona = models.Persona(
            tenant_id=tenant_id,
            name="Strict Output Agent",
            description="Enforces output contract",
            system_prompt="Review strictly",
            focus_areas=["clarity"],
            tone="direct",
            output_requirements={
                "format": "bullet_list",
                "max_bullets": 4,
                "require_quote_excerpt": True,
                "require_actionable": True,
                "include_severity": True,
            },
            is_active=True,
        )
        db.add(persona)
        db.commit()
        db.refresh(persona)

        doc = models.Document(tenant_id=tenant_id, title="Output Contract Doc")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        version = models.DocumentVersion(
            tenant_id=tenant_id,
            document_id=doc.id,
            version_label="v1",
            content="Alpha beta gamma delta",
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

        monkeypatch.setattr(
            "app.reviews.worker.generate_completion",
            lambda _prompt: '- "Alpha" :: tighten intro',
        )

        run_review_job(job.id, tenant_id)

        comments = (
            db.query(models.Comment)
            .filter(models.Comment.document_version_id == version.id)
            .all()
        )
        assert len(comments) == 1
        metadata = comments[0].output_metadata or {}
        violations = metadata.get("violations", [])
        assert "missing_severity" in violations
    finally:
        db.close()
