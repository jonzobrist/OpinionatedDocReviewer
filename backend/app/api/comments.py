from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id
from app.crud.comment import create_comment, list_comments_by_version
from app.crud.document_version import get_version
from app.crud.persona import get_persona
from app.schemas.comment import CommentCreate, CommentRead

router = APIRouter(prefix="/comments", tags=["comments"])


@router.get("", response_model=list[CommentRead])
def list_by_version(
    document_version_id: int,
    review_job_id: int | None = None,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[CommentRead]:
    version = get_version(db, tenant_id, document_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
    return list_comments_by_version(db, tenant_id, document_version_id, review_job_id)


@router.post("", response_model=CommentRead, status_code=201)
def create(
    payload: CommentCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> CommentRead:
    version = get_version(db, tenant_id, payload.document_version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
    persona = get_persona(db, tenant_id, payload.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    if payload.end_offset < payload.start_offset:
        raise HTTPException(status_code=400, detail="Invalid offset range")
    return create_comment(db, tenant_id, payload)
