from sqlalchemy.orm import Session

from app.db import models
from app.schemas.document_version import DocumentVersionCreate
from app.core.config import settings
from app.reviews.git_repo import ensure_repo, write_and_commit


def create_version(
    db: Session,
    tenant_id: str,
    document_id: int,
    data: DocumentVersionCreate,
) -> models.DocumentVersion:
    if settings.DOC_REPO_ENABLED:
        repo = ensure_repo(tenant_id, document_id)
        write_and_commit(repo, data.content, f"{data.version_label}")
    version = models.DocumentVersion(
        tenant_id=tenant_id,
        document_id=document_id,
        version_label=data.version_label,
        content=data.content,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def list_versions(db: Session, tenant_id: str, document_id: int) -> list[models.DocumentVersion]:
    return (
        db.query(models.DocumentVersion)
        .filter(
            models.DocumentVersion.tenant_id == tenant_id,
            models.DocumentVersion.document_id == document_id,
        )
        .order_by(models.DocumentVersion.id.asc())
        .all()
    )


def get_version(
    db: Session, tenant_id: str, version_id: int
) -> models.DocumentVersion | None:
    return (
        db.query(models.DocumentVersion)
        .filter(
            models.DocumentVersion.tenant_id == tenant_id,
            models.DocumentVersion.id == version_id,
        )
        .first()
    )
