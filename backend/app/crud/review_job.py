from sqlalchemy.orm import Session

from app.db import models
from app.schemas.review_job import ReviewJobCreate


def create_job(db: Session, tenant_id: str, data: ReviewJobCreate) -> models.ReviewJob:
    job = models.ReviewJob(
        tenant_id=tenant_id,
        document_version_id=data.document_version_id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_jobs(db: Session, tenant_id: str) -> list[models.ReviewJob]:
    return (
        db.query(models.ReviewJob)
        .filter(models.ReviewJob.tenant_id == tenant_id)
        .order_by(models.ReviewJob.id.asc())
        .all()
    )
