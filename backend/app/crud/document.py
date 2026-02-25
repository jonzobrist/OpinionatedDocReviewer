from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db import models
from app.schemas.document import DocumentCreate, DocumentUpdate


def create_document(db: Session, tenant_id: str, data: DocumentCreate) -> models.Document:
    doc = models.Document(tenant_id=tenant_id, title=data.title, tags=list(data.tags or []))
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def list_documents(
    db: Session, tenant_id: str, include_archived: bool = False
) -> list[models.Document]:
    query = db.query(models.Document).filter(models.Document.tenant_id == tenant_id)
    if not include_archived:
        query = query.filter(models.Document.is_archived.is_(False))
    return query.order_by(models.Document.id.asc()).all()


def get_document(db: Session, tenant_id: str, document_id: int) -> models.Document | None:
    return (
        db.query(models.Document)
        .filter(
            models.Document.tenant_id == tenant_id,
            models.Document.id == document_id,
        )
        .first()
    )


def update_document(
    db: Session, tenant_id: str, document_id: int, data: DocumentUpdate
) -> models.Document | None:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(doc, key, value)
    db.commit()
    db.refresh(doc)
    return doc


def delete_document(db: Session, tenant_id: str, document_id: int) -> bool:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        return False
    db.delete(doc)
    db.commit()
    return True


def set_document_archived(
    db: Session, tenant_id: str, document_id: int, archived: bool
) -> models.Document | None:
    doc = get_document(db, tenant_id, document_id)
    if not doc:
        return None
    doc.is_archived = archived
    doc.archived_at = datetime.now(timezone.utc) if archived else None
    db.commit()
    db.refresh(doc)
    return doc


def list_document_library(
    db: Session, tenant_id: str, include_archived: bool = True
) -> list[dict]:
    docs = list_documents(db, tenant_id, include_archived=include_archived)
    entries: list[dict] = []
    for doc in docs:
        latest_version = (
            db.query(models.DocumentVersion)
            .filter(
                models.DocumentVersion.tenant_id == tenant_id,
                models.DocumentVersion.document_id == doc.id,
            )
            .order_by(models.DocumentVersion.created_at.desc(), models.DocumentVersion.id.desc())
            .first()
        )
        latest_review = None
        if latest_version:
            latest_review = (
                db.query(models.ReviewJob)
                .filter(
                    models.ReviewJob.tenant_id == tenant_id,
                    models.ReviewJob.document_version_id == latest_version.id,
                )
                .order_by(models.ReviewJob.created_at.desc(), models.ReviewJob.id.desc())
                .first()
            )
        latest_version_created = latest_version.created_at if latest_version else None
        latest_review_completed = latest_review.completed_at if latest_review else None
        latest_review_created = latest_review.created_at if latest_review else None
        needs_review = bool(
            latest_version
            and (
                latest_review is None
                or latest_review.status != "completed"
                or (
                    latest_review_completed is not None
                    and latest_review_completed < latest_version_created
                )
            )
        )
        entries.append(
            {
                "id": doc.id,
                "tenant_id": doc.tenant_id,
                "title": doc.title,
                "is_archived": doc.is_archived,
                "archived_at": doc.archived_at,
                "created_at": doc.created_at,
                "latest_version_id": latest_version.id if latest_version else None,
                "latest_version_label": latest_version.version_label if latest_version else None,
                "latest_version_created_at": latest_version_created,
                "latest_review_job_id": latest_review.id if latest_review else None,
                "latest_review_status": latest_review.status if latest_review else None,
                "latest_review_created_at": latest_review_created,
                "latest_review_completed_at": latest_review_completed,
                "needs_review": needs_review,
            }
        )
    return entries
