from sqlalchemy.orm import Session

from app.db import models
from app.reviews.parsing import normalize_comment_output_metadata
from app.schemas.comment import CommentCreate


def create_comment(db: Session, tenant_id: str, data: CommentCreate) -> models.Comment:
    comment = models.Comment(
        tenant_id=tenant_id,
        document_version_id=data.document_version_id,
        review_job_id=data.review_job_id,
        persona_id=data.persona_id,
        text=data.text,
        start_offset=data.start_offset,
        end_offset=data.end_offset,
        excerpt=data.excerpt,
        output_metadata=normalize_comment_output_metadata(data.output_metadata),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def list_comments_by_version(
    db: Session,
    tenant_id: str,
    document_version_id: int,
    review_job_id: int | None = None,
) -> list[models.Comment]:
    query = (
        db.query(models.Comment)
        .filter(
            models.Comment.tenant_id == tenant_id,
            models.Comment.document_version_id == document_version_id,
        )
    )
    if review_job_id is not None:
        query = query.filter(models.Comment.review_job_id == review_job_id)
    comments = query.order_by(models.Comment.id.asc()).all()
    for comment in comments:
        comment.output_metadata = normalize_comment_output_metadata(comment.output_metadata)
    return comments
