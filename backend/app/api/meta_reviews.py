from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_tenant_id
from app.db import models
from app.reviews.meta_reviewer import run_meta_review
from app.schemas.meta_review import MetaReviewCreate, MetaReviewRunRead

router = APIRouter(prefix="/meta-reviews", tags=["meta-reviews"])


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


@router.post("", response_model=MetaReviewRunRead, status_code=201)
def create_meta_review(
    payload: MetaReviewCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> models.MetaReviewRun:
    version = (
        db.query(models.DocumentVersion)
        .filter(
            models.DocumentVersion.tenant_id == tenant_id,
            models.DocumentVersion.id == payload.document_version_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
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
        raise HTTPException(status_code=503, detail=f"Meta synthesis failed: {exc}") from exc
    loaded = _load_run(db, tenant_id, run.id)
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to load synthesized run")
    loaded.comments.sort(key=lambda item: (item.start_offset, item.order_index, item.id))
    return loaded


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
        .order_by(models.MetaReviewRun.id.desc())
    )
    if review_job_id is not None:
        query = query.filter(models.MetaReviewRun.review_job_id == review_job_id)
    run = query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Meta review run not found")
    run.comments.sort(key=lambda item: (item.start_offset, item.order_index, item.id))
    return run
