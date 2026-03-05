from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import models
from app.reviews.llm_provider import get_model_label, get_provider_name
from app.reviews.quality_telemetry import (
    build_empty_review_quality_telemetry,
    normalize_review_quality_telemetry,
)
from app.schemas.review_job import ReviewJobCreate


def _attach_generation_metadata(
    db: Session,
    tenant_id: str,
    jobs: list[models.ReviewJob],
) -> None:
    if not jobs:
        return

    version_ids = sorted({job.document_version_id for job in jobs})
    generation_index_by_job_id: dict[int, int] = {}
    latest_job_id_by_version: dict[int, int] = {}
    running_index_by_version: dict[int, int] = defaultdict(int)

    version_rows = (
        db.query(models.ReviewJob.id, models.ReviewJob.document_version_id)
        .filter(
            models.ReviewJob.tenant_id == tenant_id,
            models.ReviewJob.document_version_id.in_(version_ids),
        )
        .order_by(models.ReviewJob.document_version_id.asc(), models.ReviewJob.id.asc())
        .all()
    )
    for review_job_id, document_version_id in version_rows:
        running_index_by_version[document_version_id] += 1
        generation_index_by_job_id[review_job_id] = running_index_by_version[document_version_id]
        latest_job_id_by_version[document_version_id] = review_job_id

    job_ids = [job.id for job in jobs]
    comment_count_rows = (
        db.query(models.Comment.review_job_id, func.count(models.Comment.id))
        .filter(
            models.Comment.tenant_id == tenant_id,
            models.Comment.review_job_id.is_not(None),
            models.Comment.review_job_id.in_(job_ids),
        )
        .group_by(models.Comment.review_job_id)
        .all()
    )
    comment_count_by_job_id = {review_job_id: int(count) for review_job_id, count in comment_count_rows}

    for job in jobs:
        job.generation_index = generation_index_by_job_id.get(job.id)
        latest_for_version = latest_job_id_by_version.get(job.document_version_id)
        job.is_latest_for_version = latest_for_version == job.id if latest_for_version is not None else None
        job.comment_count = comment_count_by_job_id.get(job.id, 0)


def create_job(db: Session, tenant_id: str, data: ReviewJobCreate) -> models.ReviewJob:
    job = models.ReviewJob(
        tenant_id=tenant_id,
        document_version_id=data.document_version_id,
        status="queued",
        trigger=data.trigger or "auto",
        provider=get_provider_name(),
        model=get_model_label(),
        quality_telemetry=build_empty_review_quality_telemetry(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    _attach_generation_metadata(db, tenant_id, [job])
    job.quality_telemetry = normalize_review_quality_telemetry(job.quality_telemetry)
    return job


def list_jobs(
    db: Session, tenant_id: str, document_version_id: int | None = None
) -> list[models.ReviewJob]:
    query = db.query(models.ReviewJob).filter(models.ReviewJob.tenant_id == tenant_id)
    if document_version_id is not None:
        query = query.filter(models.ReviewJob.document_version_id == document_version_id)
    jobs = query.order_by(models.ReviewJob.id.asc()).all()
    _attach_generation_metadata(db, tenant_id, jobs)
    for job in jobs:
        job.quality_telemetry = normalize_review_quality_telemetry(job.quality_telemetry)
    return jobs


def get_latest_job_for_version(
    db: Session, tenant_id: str, document_version_id: int
) -> models.ReviewJob | None:
    job = (
        db.query(models.ReviewJob)
        .filter(
            models.ReviewJob.tenant_id == tenant_id,
            models.ReviewJob.document_version_id == document_version_id,
        )
        .order_by(models.ReviewJob.id.desc())
        .first()
    )
    if job is not None:
        _attach_generation_metadata(db, tenant_id, [job])
        job.quality_telemetry = normalize_review_quality_telemetry(job.quality_telemetry)
    return job
