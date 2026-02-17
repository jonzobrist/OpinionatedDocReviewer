from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant_id, require_admin_user
from app.db import models
from app.db.init_db import seed_default_admin_user
from app.schemas.admin import (
    AdminActionRead,
    AdminJobRead,
    AdminOverview,
    AdminUserCreate,
    AdminUserRead,
    AdminUserUpdate,
    DocumentPermissionCreate,
    DocumentPermissionRead,
    DocumentPermissionUpdate,
)
from app.core.config import settings

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_user)],
)


def _get_user(db: Session, tenant_id: str, user_id: int) -> models.User | None:
    return (
        db.query(models.User)
        .filter(models.User.tenant_id == tenant_id, models.User.id == user_id)
        .first()
    )


def _get_document(db: Session, tenant_id: str, document_id: int) -> models.Document | None:
    return (
        db.query(models.Document)
        .filter(models.Document.tenant_id == tenant_id, models.Document.id == document_id)
        .first()
    )


def _repo_info(tenant_id: str) -> dict:
    repo_root = Path(settings.DOC_REPO_ROOT).expanduser()
    tenant_root = repo_root / tenant_id
    repo_count = 0
    if tenant_root.exists():
        repo_count = sum(1 for child in tenant_root.iterdir() if child.is_dir())
    return {
        "enabled": settings.DOC_REPO_ENABLED,
        "root": str(repo_root),
        "tenant_root": str(tenant_root),
        "repository_count": repo_count,
    }


def _job_row_to_read(row: tuple) -> AdminJobRead:
    job, version, document = row
    return AdminJobRead(
        id=job.id,
        document_version_id=job.document_version_id,
        document_id=document.id,
        document_title=document.title,
        status=job.status,
        trigger=job.trigger,
        provider=job.provider,
        model=job.model,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _log_admin_action(
    db: Session,
    tenant_id: str,
    admin_user: models.User | None,
    action: str,
    target_type: str,
    target_id: int | None,
    details: str | None = None,
) -> None:
    db.add(
        models.AdminActionLog(
            tenant_id=tenant_id,
            actor_user_id=admin_user.id if admin_user else None,
            actor_email=admin_user.email if admin_user else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    )


@router.get("/overview", response_model=AdminOverview)
def get_overview(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> AdminOverview:
    seed_default_admin_user(tenant_id=tenant_id, db=db)
    users_total = (
        db.query(func.count(models.User.id)).filter(models.User.tenant_id == tenant_id).scalar() or 0
    )
    users_admin = (
        db.query(func.count(models.User.id))
        .filter(models.User.tenant_id == tenant_id, models.User.role == "admin")
        .scalar()
        or 0
    )
    users_active = (
        db.query(func.count(models.User.id))
        .filter(models.User.tenant_id == tenant_id, models.User.is_active.is_(True))
        .scalar()
        or 0
    )
    documents_total = (
        db.query(func.count(models.Document.id))
        .filter(models.Document.tenant_id == tenant_id)
        .scalar()
        or 0
    )
    documents_archived = (
        db.query(func.count(models.Document.id))
        .filter(models.Document.tenant_id == tenant_id, models.Document.is_archived.is_(True))
        .scalar()
        or 0
    )

    jobs_query = (
        db.query(models.ReviewJob, models.DocumentVersion, models.Document)
        .join(
            models.DocumentVersion,
            models.DocumentVersion.id == models.ReviewJob.document_version_id,
        )
        .join(models.Document, models.Document.id == models.DocumentVersion.document_id)
        .filter(models.ReviewJob.tenant_id == tenant_id)
        .order_by(models.ReviewJob.created_at.desc())
    )
    recent_rows = jobs_query.limit(50).all()
    in_progress_rows = [
        row
        for row in recent_rows
        if row[0].status in {"queued", "running"}
    ][:20]
    jobs_completed = (
        db.query(func.count(models.ReviewJob.id))
        .filter(models.ReviewJob.tenant_id == tenant_id, models.ReviewJob.status == "completed")
        .scalar()
        or 0
    )
    jobs_failed = (
        db.query(func.count(models.ReviewJob.id))
        .filter(models.ReviewJob.tenant_id == tenant_id, models.ReviewJob.status == "failed")
        .scalar()
        or 0
    )
    actions = (
        db.query(models.AdminActionLog)
        .filter(models.AdminActionLog.tenant_id == tenant_id)
        .order_by(models.AdminActionLog.created_at.desc())
        .limit(30)
        .all()
    )

    return AdminOverview(
        tenant_id=tenant_id,
        repository=_repo_info(tenant_id),
        users={
            "total": users_total,
            "admins": users_admin,
            "active": users_active,
        },
        documents={
            "total": documents_total,
            "archived": documents_archived,
            "active": max(0, documents_total - documents_archived),
        },
        jobs={
            "in_progress": len(in_progress_rows),
            "completed": jobs_completed,
            "failed": jobs_failed,
            "recent_total": len(recent_rows),
        },
        in_progress_jobs=[_job_row_to_read(row) for row in in_progress_rows],
        recent_jobs=[_job_row_to_read(row) for row in recent_rows],
        recent_actions=actions,
    )


@router.get("/users", response_model=list[AdminUserRead])
def list_users(
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[models.User]:
    seed_default_admin_user(tenant_id=tenant_id, db=db)
    return (
        db.query(models.User)
        .filter(models.User.tenant_id == tenant_id)
        .order_by(models.User.created_at.asc())
        .all()
    )


@router.post("/users", response_model=AdminUserRead, status_code=201)
def create_user(
    payload: AdminUserCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    admin_user: models.User = Depends(require_admin_user),
) -> models.User:
    existing = (
        db.query(models.User)
        .filter(models.User.tenant_id == tenant_id, models.User.email == payload.email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="User with this email already exists")
    user = models.User(
        tenant_id=tenant_id,
        name=payload.name,
        email=payload.email,
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    _log_admin_action(
        db,
        tenant_id,
        admin_user,
        action="user.create",
        target_type="user",
        target_id=None,
        details=f"email={payload.email},role={payload.role}",
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: int,
    payload: AdminUserUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    admin_user: models.User = Depends(require_admin_user),
) -> models.User:
    user = _get_user(db, tenant_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    _log_admin_action(
        db,
        tenant_id,
        admin_user,
        action="user.update",
        target_type="user",
        target_id=user.id,
        details=",".join(f"{k}={v}" for k, v in update_data.items()),
    )
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    admin_user: models.User = Depends(require_admin_user),
) -> None:
    user = _get_user(db, tenant_id, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    _log_admin_action(
        db,
        tenant_id,
        admin_user,
        action="user.delete",
        target_type="user",
        target_id=user.id,
        details=user.email,
    )
    db.delete(user)
    db.commit()


@router.get("/permissions", response_model=list[DocumentPermissionRead])
def list_permissions(
    document_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[DocumentPermissionRead]:
    query = (
        db.query(models.DocumentPermission, models.User)
        .join(models.User, models.User.id == models.DocumentPermission.user_id)
        .filter(models.DocumentPermission.tenant_id == tenant_id)
    )
    if document_id is not None:
        query = query.filter(models.DocumentPermission.document_id == document_id)
    rows = query.order_by(models.DocumentPermission.created_at.desc()).all()
    return [
        DocumentPermissionRead(
            id=perm.id,
            tenant_id=perm.tenant_id,
            document_id=perm.document_id,
            user_id=perm.user_id,
            permission_level=perm.permission_level,
            created_at=perm.created_at,
            user_name=user.name,
            user_email=user.email,
        )
        for perm, user in rows
    ]


@router.post("/permissions", response_model=DocumentPermissionRead, status_code=201)
def create_permission(
    payload: DocumentPermissionCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    admin_user: models.User = Depends(require_admin_user),
) -> DocumentPermissionRead:
    user = _get_user(db, tenant_id, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    document = _get_document(db, tenant_id, payload.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    existing = (
        db.query(models.DocumentPermission)
        .filter(
            models.DocumentPermission.tenant_id == tenant_id,
            models.DocumentPermission.document_id == payload.document_id,
            models.DocumentPermission.user_id == payload.user_id,
        )
        .first()
    )
    if existing:
        existing.permission_level = payload.permission_level
        _log_admin_action(
            db,
            tenant_id,
            admin_user,
            action="permission.update",
            target_type="permission",
            target_id=existing.id,
            details=f"doc={payload.document_id},user={payload.user_id},level={payload.permission_level}",
        )
        db.commit()
        db.refresh(existing)
        perm = existing
    else:
        perm = models.DocumentPermission(
            tenant_id=tenant_id,
            document_id=payload.document_id,
            user_id=payload.user_id,
            permission_level=payload.permission_level,
        )
        db.add(perm)
        _log_admin_action(
            db,
            tenant_id,
            admin_user,
            action="permission.create",
            target_type="permission",
            target_id=None,
            details=f"doc={payload.document_id},user={payload.user_id},level={payload.permission_level}",
        )
        db.commit()
        db.refresh(perm)
    return DocumentPermissionRead(
        id=perm.id,
        tenant_id=perm.tenant_id,
        document_id=perm.document_id,
        user_id=perm.user_id,
        permission_level=perm.permission_level,
        created_at=perm.created_at,
        user_name=user.name,
        user_email=user.email,
    )


@router.patch("/permissions/{permission_id}", response_model=DocumentPermissionRead)
def update_permission(
    permission_id: int,
    payload: DocumentPermissionUpdate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    admin_user: models.User = Depends(require_admin_user),
) -> DocumentPermissionRead:
    perm = (
        db.query(models.DocumentPermission)
        .filter(
            models.DocumentPermission.tenant_id == tenant_id,
            models.DocumentPermission.id == permission_id,
        )
        .first()
    )
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    user = _get_user(db, tenant_id, perm.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    perm.permission_level = payload.permission_level
    _log_admin_action(
        db,
        tenant_id,
        admin_user,
        action="permission.update",
        target_type="permission",
        target_id=perm.id,
        details=f"level={payload.permission_level}",
    )
    db.commit()
    db.refresh(perm)
    return DocumentPermissionRead(
        id=perm.id,
        tenant_id=perm.tenant_id,
        document_id=perm.document_id,
        user_id=perm.user_id,
        permission_level=perm.permission_level,
        created_at=perm.created_at,
        user_name=user.name,
        user_email=user.email,
    )


@router.delete("/permissions/{permission_id}", status_code=204)
def delete_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
    admin_user: models.User = Depends(require_admin_user),
) -> None:
    perm = (
        db.query(models.DocumentPermission)
        .filter(
            models.DocumentPermission.tenant_id == tenant_id,
            models.DocumentPermission.id == permission_id,
        )
        .first()
    )
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    _log_admin_action(
        db,
        tenant_id,
        admin_user,
        action="permission.delete",
        target_type="permission",
        target_id=perm.id,
        details=f"doc={perm.document_id},user={perm.user_id}",
    )
    db.delete(perm)
    db.commit()


@router.get("/actions", response_model=list[AdminActionRead])
def list_actions(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> list[models.AdminActionLog]:
    return (
        db.query(models.AdminActionLog)
        .filter(models.AdminActionLog.tenant_id == tenant_id)
        .order_by(models.AdminActionLog.created_at.desc())
        .limit(limit)
        .all()
    )
