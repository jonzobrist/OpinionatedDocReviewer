import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_tenant_id,
    get_request_user,
    require_document_permission,
)
from app.db import models
from app.crud.document_version import get_version
from app.crud.review_job import create_job, list_jobs, get_latest_job_for_version
from app.reviews.queue import enqueue_review_job
from app.reviews.worker import run_review_job, retry_failed_persona_in_job
from app.core.config import settings
from app.schemas.review_job import ReviewJobCreate, ReviewJobRead

router = APIRouter(prefix="/review-jobs", tags=["review-jobs"])
logger = logging.getLogger(__name__)


@router.get("", response_model=list[ReviewJobRead])
def list_all(
    document_version_id: int | None = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> list[ReviewJobRead]:
    jobs = list_jobs(db, tenant_id, document_version_id)
    if current_user.role == "admin":
        return jobs
    allowed: list[models.ReviewJob] = []
    for job in jobs:
        version = get_version(db, tenant_id, job.document_version_id)
        if not version:
            continue
        try:
            require_document_permission(db, tenant_id, current_user, version.document_id, "viewer")
            allowed.append(job)
        except HTTPException:
            continue
    return allowed


@router.post("", response_model=ReviewJobRead, status_code=201)
def create(
    payload: ReviewJobCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> ReviewJobRead:
    version = get_version(db, tenant_id, payload.document_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
    require_document_permission(db, tenant_id, current_user, version.document_id, "editor")
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
        logger.exception("enqueue_review_job_failed review_job_id=%s tenant_id=%s", job.id, tenant_id)
        raise HTTPException(status_code=503, detail="Failed to enqueue review job")

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
    current_user: models.User = Depends(get_request_user),
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
    version = get_version(db, tenant_id, existing.document_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
    require_document_permission(db, tenant_id, current_user, version.document_id, "editor")
    try:
        added = retry_failed_persona_in_job(review_job_id, tenant_id, persona_id)
    except Exception as exc:
        logger.exception(
            "retry_failed_persona_error review_job_id=%s persona_id=%s tenant_id=%s",
            review_job_id,
            persona_id,
            tenant_id,
        )
        raise HTTPException(status_code=503, detail="Retry failed") from exc
    if added == 0:
        raise HTTPException(status_code=404, detail="Persona or document context not found")
    return {"status": "retried", "review_job_id": review_job_id, "persona_id": persona_id, "comments_added": added}
