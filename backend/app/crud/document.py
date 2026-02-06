from sqlalchemy.orm import Session

from app.db import models
from app.schemas.document import DocumentCreate, DocumentUpdate


def create_document(db: Session, tenant_id: str, data: DocumentCreate) -> models.Document:
    doc = models.Document(tenant_id=tenant_id, title=data.title)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def list_documents(db: Session, tenant_id: str) -> list[models.Document]:
    return (
        db.query(models.Document)
        .filter(models.Document.tenant_id == tenant_id)
        .order_by(models.Document.id.asc())
        .all()
    )


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
