from app.db import models
from app.db.init_db import seed_default_personas
from app.db.session import SessionLocal
from app.reviews.worker import run_review_job


def test_review_worker_generates_comments(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test"
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

        def _fake_generate_comments(persona, content):
            return ["- Review: clarify \"world\" term."]

        monkeypatch.setattr("app.reviews.worker.generate_comments", _fake_generate_comments)

        run_review_job(job.id, tenant_id)

        comments = (
            db.query(models.Comment)
            .filter(models.Comment.document_version_id == version.id)
            .all()
        )
        assert len(comments) > 0
        assert comments[0].excerpt in ("world", None)
    finally:
        db.close()
