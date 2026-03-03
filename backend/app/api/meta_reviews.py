from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_tenant_id
from app.db import models
from app.reviews.meta_reviewer import (
    ensure_meta_review_run,
    normalize_meta_review_run_state,
    run_meta_review,
)
from app.schemas.meta_review import (
    MetaReviewCreate,
    MetaReviewEnsureRead,
    MetaReviewEnsureRequest,
    MetaReviewRunRead,
)

router = APIRouter(prefix="/meta-reviews", tags=["meta-reviews"])
logger = logging.getLogger(__name__)


def _load_run(
    db: Session,
    tenant_id: str,
    run_id: int,
) -> models.MetaReviewRun | None:
    return (
        db.query(models.MetaReviewRun)
        .options(
            selectinload(models.MetaReviewRun.comments).selectinload(models.MetaComment.sources)
        )
        .filter(models.MetaReviewRun.tenant_id == tenant_id, models.MetaReviewRun.id == run_id)
        .first()
    )


def _ensure_document_version_exists(db: Session, tenant_id: str, document_version_id: int) -> None:
    version = (
        db.query(models.DocumentVersion)
        .filter(
            models.DocumentVersion.tenant_id == tenant_id,
            models.DocumentVersion.id == document_version_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")


def _prepare_run_for_response(run: models.MetaReviewRun) -> models.MetaReviewRun:
    normalize_meta_review_run_state(run)
    run.comments.sort(key=lambda item: (-item.rank_score, item.start_offset, item.order_index, item.id))
    return run


@router.post("", response_model=MetaReviewRunRead, status_code=201)
def create_meta_review(
    payload: MetaReviewCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> models.MetaReviewRun:
    _ensure_document_version_exists(db, tenant_id, payload.document_version_id)
    try:
        run = run_meta_review(
            db=db,
            tenant_id=tenant_id,
            document_version_id=payload.document_version_id,
            review_job_id=payload.review_job_id,
            force=payload.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "meta_synthesis_failed tenant_id=%s document_version_id=%s review_job_id=%s",
            tenant_id,
            payload.document_version_id,
            payload.review_job_id,
        )
        raise HTTPException(status_code=503, detail="Meta synthesis failed") from exc
    loaded = _load_run(db, tenant_id, run.id)
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to load synthesized run")
    return _prepare_run_for_response(loaded)


@router.post("/ensure", response_model=MetaReviewEnsureRead)
def ensure_meta_review(
    payload: MetaReviewEnsureRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    _ensure_document_version_exists(db, tenant_id, payload.document_version_id)
    try:
        ensured = ensure_meta_review_run(
            db=db,
            tenant_id=tenant_id,
            document_version_id=payload.document_version_id,
            review_job_id=payload.review_job_id,
            force=payload.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "meta_ensure_failed tenant_id=%s document_version_id=%s review_job_id=%s",
            tenant_id,
            payload.document_version_id,
            payload.review_job_id,
        )
        raise HTTPException(status_code=503, detail="Meta synthesis failed") from exc

    loaded = _load_run(db, tenant_id, ensured.run.id)
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to load synthesized run")

    run_payload = MetaReviewRunRead.model_validate(_prepare_run_for_response(loaded)).model_dump()
    run_payload["resolution"] = ensured.resolution
    return run_payload


@router.get("/latest", response_model=MetaReviewRunRead)
def get_latest_meta_review(
    document_version_id: int = Query(gt=0),
    review_job_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> models.MetaReviewRun:
    query = (
        db.query(models.MetaReviewRun)
        .options(
            selectinload(models.MetaReviewRun.comments).selectinload(models.MetaComment.sources)
        )
        .filter(
            models.MetaReviewRun.tenant_id == tenant_id,
            models.MetaReviewRun.document_version_id == document_version_id,
        )
    )
    if review_job_id is not None:
        query = query.filter(models.MetaReviewRun.review_job_id == review_job_id).order_by(
            models.MetaReviewRun.created_at.desc(),
            models.MetaReviewRun.id.desc(),
        )
    else:
        # Stale-run guard: prioritize the newest review context first, then recency.
        # Tie-break order for unscoped latest: review_job_id (desc, NULL last), created_at desc, id desc.
        query = query.order_by(
            func.coalesce(models.MetaReviewRun.review_job_id, -1).desc(),
            models.MetaReviewRun.created_at.desc(),
            models.MetaReviewRun.id.desc(),
        )
    run = query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Meta review run not found")
    return _prepare_run_for_response(run)
