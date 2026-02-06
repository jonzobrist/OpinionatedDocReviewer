from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id
from app.crud.document import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    update_document,
)
from app.crud.document_version import create_version, get_version, list_versions
from app.schemas.document import DocumentCreate, DocumentRead, DocumentUpdate
from app.schemas.document_version import DocumentVersionCreate, DocumentVersionRead
from app.reviews.git_repo import ensure_repo
from app.reviews.git_history import list_commits

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentRead])
def list_all(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[DocumentRead]:
    return list_documents(db, tenant_id)


@router.post("", response_model=DocumentRead, status_code=201)
def create(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentRead:
    return create_document(db, tenant_id, payload)


@router.get("/{document_id}", response_model=DocumentRead)
def get_one(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentRead:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.patch("/{document_id}", response_model=DocumentRead)
def update(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentRead:
    doc = update_document(db, tenant_id, document_id, payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id}", status_code=204)
def delete(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> None:
    success = delete_document(db, tenant_id, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/{document_id}/versions", response_model=list[DocumentVersionRead])
def list_doc_versions(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[DocumentVersionRead]:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return list_versions(db, tenant_id, document_id)


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionRead,
    status_code=201,
)
def create_doc_version(
    document_id: int,
    payload: DocumentVersionCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentVersionRead:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return create_version(db, tenant_id, document_id, payload)


@router.get("/versions/{version_id}", response_model=DocumentVersionRead)
def get_version_by_id(
    version_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentVersionRead:
    version = get_version(db, tenant_id, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
    return version


@router.get("/{document_id}/history")
def get_history(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[dict]:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    repo = ensure_repo(tenant_id, document_id)
    commits = list_commits(repo, limit=50)
    return [
        {
            "sha": commit.sha,
            "message": commit.message,
            "authored_at": commit.authored_at.isoformat(),
        }
        for commit in commits
    ]
