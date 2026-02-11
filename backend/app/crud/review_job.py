from sqlalchemy.orm import Session

from app.db import models
from app.reviews.llm_provider import get_model_label, get_provider_name
from app.schemas.review_job import ReviewJobCreate


def create_job(db: Session, tenant_id: str, data: ReviewJobCreate) -> models.ReviewJob:
    job = models.ReviewJob(
        tenant_id=tenant_id,
        document_version_id=data.document_version_id,
        status="queued",
        trigger=data.trigger or "auto",
        provider=get_provider_name(),
        model=get_model_label(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def list_jobs(
    db: Session, tenant_id: str, document_version_id: int | None = None
) -> list[models.ReviewJob]:
    query = db.query(models.ReviewJob).filter(models.ReviewJob.tenant_id == tenant_id)
    if document_version_id is not None:
        query = query.filter(models.ReviewJob.document_version_id == document_version_id)
    return query.order_by(models.ReviewJob.id.asc()).all()


def get_latest_job_for_version(
    db: Session, tenant_id: str, document_version_id: int
) -> models.ReviewJob | None:
    return (
        db.query(models.ReviewJob)
        .filter(
            models.ReviewJob.tenant_id == tenant_id,
            models.ReviewJob.document_version_id == document_version_id,
        )
        .order_by(models.ReviewJob.id.desc())
        .first()
    )
