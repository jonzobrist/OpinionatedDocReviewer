from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id
from app.db import models
from app.crud.document_version import get_version
from app.crud.review_job import create_job, list_jobs, get_latest_job_for_version
from app.reviews.queue import enqueue_review_job
from app.reviews.worker import run_review_job, retry_failed_persona_in_job
from app.core.config import settings
from app.schemas.review_job import ReviewJobCreate, ReviewJobRead

router = APIRouter(prefix="/review-jobs", tags=["review-jobs"])


@router.get("", response_model=list[ReviewJobRead])
def list_all(
    document_version_id: int | None = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[ReviewJobRead]:
    return list_jobs(db, tenant_id, document_version_id)


@router.post("", response_model=ReviewJobRead, status_code=201)
def create(
    payload: ReviewJobCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> ReviewJobRead:
    version = get_version(db, tenant_id, payload.document_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
    trigger = payload.trigger or "auto"
    if trigger == "auto":
        existing = get_latest_job_for_version(db, tenant_id, payload.document_version_id)
        if existing and existing.status in {"queued", "running", "completed"}:
            return existing
    job = create_job(db, tenant_id, payload)
    try:
        enqueue_review_job(job.id, tenant_id)
    except Exception as exc:
        if settings.REVIEW_INLINE:
            run_review_job(job.id, tenant_id)
            db.refresh(job)
            return job
        job.status = "failed"
        db.commit()
        raise HTTPException(status_code=503, detail=f"Failed to enqueue review job: {exc}")

    if settings.REVIEW_INLINE:
        run_review_job(job.id, tenant_id)
        db.refresh(job)
    return job


@router.post("/{review_job_id}/retry-persona/{persona_id}")
def retry_persona(
    review_job_id: int,
    persona_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    existing = (
        db.query(models.ReviewJob)
        .filter(
            models.ReviewJob.id == review_job_id,
            models.ReviewJob.tenant_id == tenant_id,
        )
        .first()
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Review job not found")
    try:
        added = retry_failed_persona_in_job(review_job_id, tenant_id, persona_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Retry failed: {exc}") from exc
    if added == 0:
        raise HTTPException(status_code=404, detail="Persona or document context not found")
    return {"status": "retried", "review_job_id": review_job_id, "persona_id": persona_id, "comments_added": added}
