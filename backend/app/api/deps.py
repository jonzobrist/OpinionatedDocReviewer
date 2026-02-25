from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.oidc import decode_access_token
from app.auth.local_auth import decode_access_token as decode_local_access_token
from app.core.config import settings
from app.db import models
from app.db.init_db import seed_default_admin_user
from app.db.session import SessionLocal
from app.security.roles import is_admin_role
from app.security.tenant import validate_tenant_id


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@dataclass
class AuthContext:
    tenant_id: str
    user: models.User
    claims: dict | None


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization bearer token is required")
    prefix = "bearer "
    if not authorization.lower().startswith(prefix):
        raise HTTPException(status_code=401, detail="Authorization must use Bearer token")
    token = authorization[len(prefix) :].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token is empty")
    return token


def _claim_str(claims: dict, key: str, fallback: str | None = None) -> str | None:
    value = claims.get(key, fallback)
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _is_admin_from_claims(claims: dict) -> bool:
    roles_key = settings.OIDC_ROLES_CLAIM
    admin_role = settings.OIDC_ADMIN_ROLE.strip().lower()
    if not admin_role:
        return False
    roles = claims.get(roles_key)
    if isinstance(roles, str):
        role_values = [part.strip().lower() for part in roles.split(",") if part.strip()]
    elif isinstance(roles, list):
        role_values = [str(item).strip().lower() for item in roles if str(item).strip()]
    else:
        role_values = []
    return admin_role in role_values


def _get_or_create_user(
    db: Session,
    tenant_id: str,
    email: str,
    name: str | None,
    is_admin: bool,
) -> models.User:
    user = (
        db.query(models.User)
        .filter(models.User.tenant_id == tenant_id, models.User.email == email)
        .first()
    )
    role = "system_admin" if is_admin else "reader"
    if user:
        user.name = name or user.name or email
        user.role = role
        user.is_active = True
        if user.account_state in {"disabled", "locked"}:
            user.account_state = "active"
        db.commit()
        db.refresh(user)
        return user
    user = models.User(
        tenant_id=tenant_id,
        name=name or email,
        email=email,
        role=role,
        is_active=True,
        account_state="active",
        email_verified_at=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth_context_from_headers(
    db: Session,
    x_tenant_id: str | None,
    x_user_email: str | None,
    x_user_id: str | None,
) -> AuthContext:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required")
    tenant_id = validate_tenant_id(x_tenant_id)
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
        query = query.filter(models.User.role.in_(["admin", "project_admin", "system_admin"]))
    user = query.first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="User access denied")
    return AuthContext(tenant_id=tenant_id, user=user, claims=None)


def _auth_context_from_oidc(
    db: Session,
    authorization: str | None,
) -> AuthContext:
    token = _extract_bearer_token(authorization)
    claims = decode_access_token(token)
    tenant_claim = _claim_str(claims, settings.OIDC_TENANT_CLAIM, settings.DEFAULT_TENANT_ID)
    if not tenant_claim:
        raise HTTPException(status_code=401, detail="Tenant claim missing in token")
    tenant_id = validate_tenant_id(tenant_claim)
    email = _claim_str(claims, settings.OIDC_EMAIL_CLAIM)
    if not email:
        sub = _claim_str(claims, "sub")
        if not sub:
            raise HTTPException(status_code=401, detail="Token missing both email and sub claims")
        email = f"{sub}@oidc.local"
    name = _claim_str(claims, settings.OIDC_NAME_CLAIM, email)
    user = _get_or_create_user(
        db=db,
        tenant_id=tenant_id,
        email=email,
        name=name,
        is_admin=_is_admin_from_claims(claims),
    )
    return AuthContext(tenant_id=tenant_id, user=user, claims=claims)


def _auth_context_from_local_token(
    db: Session,
    authorization: str | None,
) -> AuthContext:
    token = _extract_bearer_token(authorization)
    claims = decode_local_access_token(token)
    tenant_claim = claims.get("tenant_id")
    if not isinstance(tenant_claim, str) or not tenant_claim.strip():
        raise HTTPException(status_code=401, detail="Token missing tenant_id")
    tenant_id = validate_tenant_id(tenant_claim)
    user_id_raw = claims.get("sub")
    try:
        user_id = int(str(user_id_raw))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Token missing valid subject") from exc
    user = (
        db.query(models.User)
        .filter(models.User.tenant_id == tenant_id, models.User.id == user_id)
        .first()
    )
    if not user or not user.is_active or user.account_state in {"disabled", "locked"}:
        raise HTTPException(status_code=403, detail="User access denied")
    return AuthContext(tenant_id=tenant_id, user=user, claims=claims)


def _is_local_request(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


def get_auth_context(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> AuthContext:
    cached = getattr(request.state, "auth_context", None)
    if isinstance(cached, AuthContext):
        return cached
    mode = settings.AUTH_MODE.strip().lower()
    if mode == "oidc":
        if (
            not authorization
            and settings.OIDC_ALLOW_LOCAL_HEADER_FALLBACK
            and _is_local_request(request)
        ):
            context = _auth_context_from_headers(
                db=db,
                x_tenant_id=x_tenant_id,
                x_user_email=x_user_email,
                x_user_id=x_user_id,
            )
        else:
            context = _auth_context_from_oidc(db=db, authorization=authorization)
    elif mode == "header":
        context = _auth_context_from_headers(
            db=db,
            x_tenant_id=x_tenant_id,
            x_user_email=x_user_email,
            x_user_id=x_user_id,
        )
    elif mode == "local":
        context = _auth_context_from_local_token(db=db, authorization=authorization)
    else:
        raise HTTPException(status_code=500, detail=f"Unsupported AUTH_MODE: {settings.AUTH_MODE}")
    request.state.auth_context = context
    return context


def get_tenant_id(context: AuthContext = Depends(get_auth_context)) -> str:
    return context.tenant_id


def get_request_user(context: AuthContext = Depends(get_auth_context)) -> models.User:
    if not context.user.is_active:
        raise HTTPException(status_code=403, detail="User access denied")
    return context.user


def require_admin_user(context: AuthContext = Depends(get_auth_context)) -> models.User:
    user = context.user
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Admin access denied")
    if not is_admin_role(user.role):
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


_PERM_RANK = {"viewer": 1, "editor": 2, "owner": 3}


def get_effective_document_permission(
    db: Session,
    tenant_id: str,
    user: models.User,
    document_id: int,
) -> str | None:
    if is_admin_role(user.role):
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
    return None


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
