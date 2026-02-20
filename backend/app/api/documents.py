from uuid import uuid4

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
from app.schemas.review_bundle import ReviewBundleImport, ReviewBundleImportResult
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


@router.post("/import-bundle", response_model=ReviewBundleImportResult, status_code=201)
def import_bundle(
    payload: ReviewBundleImport,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    current_user: models.User = Depends(get_request_user),
) -> ReviewBundleImportResult:
    if not payload.comments:
        raise HTTPException(status_code=422, detail="Bundle must contain at least one comment")

    doc = create_document(db, tenant_id, DocumentCreate(title=payload.document.title))
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

    version = create_version(
        db,
        tenant_id,
        doc.id,
        DocumentVersionCreate(
            version_label=payload.version.version_label,
            content=payload.version.content,
        ),
    )

    review_job: models.ReviewJob | None = None
    if payload.review_job:
        review_job_data = dict(
            tenant_id=tenant_id,
            document_version_id=version.id,
            status=payload.review_job.status,
            trigger=payload.review_job.trigger,
            provider=payload.review_job.provider,
            model=payload.review_job.model,
        )
        if payload.review_job.created_at is not None:
            review_job_data["created_at"] = payload.review_job.created_at
        if payload.review_job.completed_at is not None:
            review_job_data["completed_at"] = payload.review_job.completed_at
        review_job = models.ReviewJob(**review_job_data)
        db.add(review_job)
        db.commit()
        db.refresh(review_job)

    persona_map: dict[int, int] = {}
    persona_name_map: dict[str, int] = {}
    personas_created = 0
    for persona in payload.personas:
        existing = (
            db.query(models.Persona)
            .filter(
                models.Persona.tenant_id == tenant_id,
                models.Persona.name == persona.name,
            )
            .order_by(models.Persona.id.asc())
            .first()
        )
        if existing:
            persona_name_map[persona.name] = existing.id
            if persona.id is not None:
                persona_map[persona.id] = existing.id
            continue
        created = models.Persona(
            tenant_id=tenant_id,
            name=persona.name,
            description=persona.description,
            system_prompt=persona.system_prompt,
            focus_areas=persona.focus_areas,
            tone=persona.tone,
            reference_notes=persona.reference_notes,
            output_requirements=persona.output_requirements,
            examples=persona.examples,
            sort_order=persona.sort_order,
            color_theme=persona.color_theme,
            is_active=persona.is_active,
            is_default=False,
            is_system_locked=False,
        )
        db.add(created)
        db.commit()
        db.refresh(created)
        personas_created += 1
        persona_name_map[persona.name] = created.id
        if persona.id is not None:
            persona_map[persona.id] = created.id

    fallback_persona = (
        db.query(models.Persona)
        .filter(models.Persona.tenant_id == tenant_id)
        .order_by(models.Persona.id.asc())
        .first()
    )
    if not fallback_persona:
        fallback_persona = models.Persona(
            tenant_id=tenant_id,
            name="Imported Reviewer",
            description="Autocreated for imported bundle",
            system_prompt="Review imported content.",
            focus_areas=[],
            tone="neutral",
            output_requirements={},
            examples=[],
            is_default=False,
            is_system_locked=False,
            sort_order=999,
            is_active=True,
        )
        db.add(fallback_persona)
        db.commit()
        db.refresh(fallback_persona)
        personas_created += 1

    old_to_new_comment_ids: dict[int, int] = {}
    comments_imported = 0
    for idx, comment in enumerate(payload.comments):
        persona_id = None
        if comment.persona_id is not None:
            persona_id = persona_map.get(comment.persona_id, comment.persona_id)
        if not persona_id and comment.persona_name:
            persona_id = persona_name_map.get(comment.persona_name)
        if not persona_id:
            persona_id = fallback_persona.id
        exists = (
            db.query(models.Persona)
            .filter(
                models.Persona.tenant_id == tenant_id,
                models.Persona.id == persona_id,
            )
            .first()
        )
        if not exists:
            persona_id = fallback_persona.id
        comment_data = dict(
            tenant_id=tenant_id,
            persona_id=persona_id,
            document_version_id=version.id,
            review_job_id=review_job.id if review_job else None,
            text=comment.text,
            start_offset=max(0, comment.start_offset),
            end_offset=max(max(0, comment.start_offset) + 1, comment.end_offset),
            excerpt=comment.excerpt,
            output_metadata=comment.output_metadata or {},
        )
        if comment.created_at is not None:
            comment_data["created_at"] = comment.created_at
        created_comment = models.Comment(**comment_data)
        db.add(created_comment)
        db.commit()
        db.refresh(created_comment)
        comments_imported += 1
        if comment.id is not None:
            old_to_new_comment_ids[comment.id] = created_comment.id
        else:
            old_to_new_comment_ids[idx + 1] = created_comment.id

    meta_comments_imported = 0
    if payload.meta_review_run and payload.meta_review_run.comments:
        run_data = dict(
            tenant_id=tenant_id,
            document_version_id=version.id,
            review_job_id=review_job.id if review_job else None,
            input_hash=f"import-{uuid4().hex}",
            status=payload.meta_review_run.status,
            is_synthesized=payload.meta_review_run.is_synthesized,
            provider=payload.meta_review_run.provider,
            model=payload.meta_review_run.model,
            error_message=payload.meta_review_run.error_message,
        )
        if payload.meta_review_run.created_at is not None:
            run_data["created_at"] = payload.meta_review_run.created_at
        run = models.MetaReviewRun(**run_data)
        db.add(run)
        db.commit()
        db.refresh(run)
        for meta_comment in payload.meta_review_run.comments:
            created_meta = models.MetaComment(
                tenant_id=tenant_id,
                meta_review_run_id=run.id,
                content=meta_comment.content,
                category=meta_comment.category,
                priority=meta_comment.priority,
                start_offset=max(0, meta_comment.start_offset),
                end_offset=max(max(0, meta_comment.start_offset) + 1, meta_comment.end_offset),
                order_index=meta_comment.order_index,
                is_unsynthesized=meta_comment.is_unsynthesized,
            )
            db.add(created_meta)
            db.commit()
            db.refresh(created_meta)
            meta_comments_imported += 1
            for source in meta_comment.sources:
                source_comment_id = (
                    old_to_new_comment_ids.get(source.comment_id)
                    if source.comment_id is not None
                    else None
                )
                if not source_comment_id:
                    continue
                db.add(
                    models.MetaCommentSource(
                        tenant_id=tenant_id,
                        meta_comment_id=created_meta.id,
                        comment_id=source_comment_id,
                        reviewer_name=source.reviewer_name,
                        reviewer_id=source.reviewer_id,
                        original_comment_text=source.original_comment_text,
                    )
                )
            db.commit()

    return ReviewBundleImportResult(
        document_id=doc.id,
        version_id=version.id,
        review_job_id=review_job.id if review_job else None,
        comments_imported=comments_imported,
        personas_created=personas_created,
        meta_comments_imported=meta_comments_imported,
    )
