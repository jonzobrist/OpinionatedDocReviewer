from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import models
from app.db.init_db import seed_default_admin_user
from app.db.session import SessionLocal


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant_id(x_tenant_id: str | None = Header(default=None)) -> str:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required")
    return x_tenant_id


def require_admin_user(
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    x_user_email: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> models.User:
    seed_default_admin_user(tenant_id=tenant_id, db=db)
    if not x_user_email and not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="Admin endpoints require X-User-Email or X-User-Id header",
        )
    query = db.query(models.User).filter(models.User.tenant_id == tenant_id)
    if x_user_id:
        try:
            user_id = int(x_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="X-User-Id must be an integer") from exc
        query = query.filter(models.User.id == user_id)
    elif x_user_email:
        query = query.filter(models.User.email == x_user_email)
    user = query.first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Admin access denied")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def get_request_user(
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db),
    x_user_email: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> models.User:
    seed_default_admin_user(tenant_id=tenant_id, db=db)
    query = db.query(models.User).filter(models.User.tenant_id == tenant_id)
    if x_user_id:
        try:
            user_id = int(x_user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="X-User-Id must be an integer") from exc
        query = query.filter(models.User.id == user_id)
    elif x_user_email:
        query = query.filter(models.User.email == x_user_email)
    else:
        query = query.filter(models.User.role == "admin")
    user = query.first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="User access denied")
    return user


_PERM_RANK = {"viewer": 1, "editor": 2, "owner": 3}


def get_effective_document_permission(
    db: Session,
    tenant_id: str,
    user: models.User,
    document_id: int,
) -> str | None:
    if user.role == "admin":
        return "owner"
    direct = (
        db.query(models.DocumentPermission)
        .filter(
            models.DocumentPermission.tenant_id == tenant_id,
            models.DocumentPermission.document_id == document_id,
            models.DocumentPermission.user_id == user.id,
        )
        .first()
    )
    if direct:
        return direct.permission_level
    any_permissions = (
        db.query(func.count(models.DocumentPermission.id))
        .filter(
            models.DocumentPermission.tenant_id == tenant_id,
            models.DocumentPermission.document_id == document_id,
        )
        .scalar()
        or 0
    )
    if any_permissions > 0:
        return None
    # Backward-compatible behavior for docs that predate permission records.
    return "owner"


def require_document_permission(
    db: Session,
    tenant_id: str,
    user: models.User,
    document_id: int,
    minimum: str,
) -> None:
    level = get_effective_document_permission(db, tenant_id, user, document_id)
    if not level:
        raise HTTPException(status_code=403, detail="Document access denied")
    if _PERM_RANK.get(level, 0) < _PERM_RANK.get(minimum, 99):
        raise HTTPException(status_code=403, detail=f"{minimum} permission required")
