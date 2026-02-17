from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_tenant_id,
    get_request_user,
    get_effective_document_permission,
    require_document_permission,
)
from app.db import models
from app.crud.document import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    list_document_library,
    set_document_archived,
    update_document,
)
from app.crud.document_version import create_version, get_version, list_versions
from app.schemas.document import (
    DocumentArchiveUpdate,
    DocumentCreate,
    DocumentLibraryEntry,
    DocumentRead,
    DocumentUpdate,
)
from app.schemas.document_version import DocumentVersionCreate, DocumentVersionRead
from app.reviews.git_repo import ensure_repo
from app.reviews.git_history import list_commits

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentRead])
def list_all(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> list[DocumentRead]:
    docs = list_documents(db, tenant_id, include_archived=include_archived)
    return [
        doc
        for doc in docs
        if get_effective_document_permission(db, tenant_id, current_user, doc.id) is not None
    ]


@router.get("/library", response_model=list[DocumentLibraryEntry])
def list_library(
    include_archived: bool = True,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> list[DocumentLibraryEntry]:
    entries = list_document_library(db, tenant_id, include_archived=include_archived)
    return [
        entry
        for entry in entries
        if get_effective_document_permission(
            db,
            tenant_id,
            current_user,
            entry["id"] if isinstance(entry, dict) else entry.id,
        )
        is not None
    ]


@router.post("", response_model=DocumentRead, status_code=201)
def create(
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> DocumentRead:
    doc = create_document(db, tenant_id, payload)
    if current_user.role != "admin":
        db.add(
            models.DocumentPermission(
                tenant_id=tenant_id,
                document_id=doc.id,
                user_id=current_user.id,
                permission_level="owner",
            )
        )
        db.commit()
    return doc


@router.get("/{document_id:int}", response_model=DocumentRead)
def get_one(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> DocumentRead:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_document_permission(db, tenant_id, current_user, document_id, "viewer")
    return doc


@router.patch("/{document_id:int}", response_model=DocumentRead)
def update(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> DocumentRead:
    require_document_permission(db, tenant_id, current_user, document_id, "owner")
    doc = update_document(db, tenant_id, document_id, payload)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/{document_id:int}/archive", response_model=DocumentRead)
def archive(
    document_id: int,
    payload: DocumentArchiveUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> DocumentRead:
    require_document_permission(db, tenant_id, current_user, document_id, "owner")
    doc = set_document_archived(db, tenant_id, document_id, payload.archived)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/{document_id:int}/restore", response_model=DocumentRead)
def restore(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> DocumentRead:
    require_document_permission(db, tenant_id, current_user, document_id, "owner")
    doc = set_document_archived(db, tenant_id, document_id, archived=False)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{document_id:int}", status_code=204)
def delete(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> None:
    require_document_permission(db, tenant_id, current_user, document_id, "owner")
    success = delete_document(db, tenant_id, document_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/{document_id:int}/versions", response_model=list[DocumentVersionRead])
def list_doc_versions(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> list[DocumentVersionRead]:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_document_permission(db, tenant_id, current_user, document_id, "viewer")
    return list_versions(db, tenant_id, document_id)


@router.post(
    "/{document_id:int}/versions",
    response_model=DocumentVersionRead,
    status_code=201,
)
def create_doc_version(
    document_id: int,
    payload: DocumentVersionCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> DocumentVersionRead:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_document_permission(db, tenant_id, current_user, document_id, "editor")
    return create_version(db, tenant_id, document_id, payload)


@router.get("/versions/{version_id}", response_model=DocumentVersionRead)
def get_version_by_id(
    version_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> DocumentVersionRead:
    version = get_version(db, tenant_id, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")
    require_document_permission(db, tenant_id, current_user, version.document_id, "viewer")
    return version


@router.get("/{document_id:int}/history")
def get_history(
    document_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> list[dict]:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_document_permission(db, tenant_id, current_user, document_id, "viewer")
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
