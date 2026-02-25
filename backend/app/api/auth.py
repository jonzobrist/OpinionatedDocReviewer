from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.local_auth import (
    hash_password,
    issue_access_token,
    new_numeric_code,
    new_token,
    now_utc,
    stable_hash,
    verify_password,
)
from app.core.config import settings
from app.db import models
from app.api.deps import get_db
from app.schemas.auth import (
    AuthForgotPasswordRequest,
    AuthForgotPasswordResponse,
    AuthGenericResponse,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthLogoutResponse,
    AuthMfaChallengeRequest,
    AuthMfaChallengeResponse,
    AuthMfaVerifyRequest,
    AuthMfaVerifyResponse,
    AuthRegisterRequest,
    AuthRegisterResponse,
    AuthResetPasswordRequest,
    AuthVerifyEmailRequest,
)
from app.security.roles import KNOWN_ROLES
from app.security.tenant import validate_tenant_id

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_account(db: Session, tenant_id: str, email: str) -> models.AuthAccount | None:
    return (
        db.query(models.AuthAccount)
        .filter(
            models.AuthAccount.tenant_id == tenant_id,
            models.AuthAccount.email == email,
        )
        .first()
    )


def _is_expired(dt) -> bool:
    value = dt
    if value is None:
        return True
    if getattr(value, "tzinfo", None) is not None:
        value = value.replace(tzinfo=None)
    return value < now_utc().replace(tzinfo=None)


@router.post("/register", response_model=AuthRegisterResponse, status_code=201)
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)) -> AuthRegisterResponse:
    tenant_id = validate_tenant_id(payload.tenant_id)
    role = payload.role.strip().lower()
    if role not in KNOWN_ROLES:
        raise HTTPException(status_code=422, detail="Unsupported role")
    existing = _get_account(db, tenant_id, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="Account already exists")
    now = now_utc()
    user = models.User(
        tenant_id=tenant_id,
        name=payload.name.strip(),
        email=payload.email,
        role=role,
        is_active=True,
        account_state="pending_verification",
    )
    db.add(user)
    db.flush()
    account = models.AuthAccount(
        tenant_id=tenant_id,
        user_id=user.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        is_email_verified=False,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    raw_token = new_token()
    db.add(
        models.AuthEmailVerification(
            tenant_id=tenant_id,
            user_id=user.id,
            token_hash=stable_hash(raw_token),
            expires_at=now + timedelta(minutes=settings.AUTH_EMAIL_TOKEN_TTL_MINUTES),
        )
    )
    db.commit()
    return AuthRegisterResponse(
        user_id=user.id,
        email=payload.email,
        requires_email_verification=True,
        verification_token=raw_token if settings.AUTH_DEV_ECHO_CODES else None,
    )


@router.post("/verify-email", response_model=AuthGenericResponse)
def verify_email(payload: AuthVerifyEmailRequest, db: Session = Depends(get_db)) -> AuthGenericResponse:
    tenant_id = validate_tenant_id(payload.tenant_id)
    account = _get_account(db, tenant_id, payload.email)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    record = (
        db.query(models.AuthEmailVerification)
        .filter(
            models.AuthEmailVerification.tenant_id == tenant_id,
            models.AuthEmailVerification.user_id == account.user_id,
            models.AuthEmailVerification.token_hash == stable_hash(payload.token),
            models.AuthEmailVerification.consumed_at.is_(None),
        )
        .order_by(models.AuthEmailVerification.id.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    if _is_expired(record.expires_at):
        raise HTTPException(status_code=400, detail="Verification token expired")

    user = db.query(models.User).filter(models.User.id == account.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    record.consumed_at = now_utc()
    account.is_email_verified = True
    user.account_state = "active"
    user.email_verified_at = now_utc()
    db.commit()
    return AuthGenericResponse(ok=True)


@router.post("/login", response_model=AuthLoginResponse)
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> AuthLoginResponse:
    tenant_id = validate_tenant_id(payload.tenant_id)
    account = _get_account(db, tenant_id, payload.email)
    if not account or not verify_password(payload.password, account.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not account.is_email_verified:
        raise HTTPException(status_code=403, detail="Email verification required")
    user = db.query(models.User).filter(models.User.id == account.user_id).first()
    if not user or not user.is_active or user.account_state in {"disabled", "locked"}:
        raise HTTPException(status_code=403, detail="User access denied")

    user.last_login_at = now_utc()
    db.commit()

    ttl_seconds = int(settings.LOCAL_AUTH_ACCESS_TOKEN_TTL_MINUTES) * 60
    token = issue_access_token(
        tenant_id=tenant_id,
        user_id=user.id,
        email=user.email,
        role=user.role,
    )
    return AuthLoginResponse(
        access_token=token,
        expires_in_seconds=ttl_seconds,
        user_id=user.id,
        role=user.role,
        email=user.email,
    )


@router.post("/logout", response_model=AuthLogoutResponse)
def logout() -> AuthLogoutResponse:
    return AuthLogoutResponse(ok=True)


@router.post("/forgot-password", response_model=AuthForgotPasswordResponse)
def forgot_password(
    payload: AuthForgotPasswordRequest, db: Session = Depends(get_db)
) -> AuthForgotPasswordResponse:
    tenant_id = validate_tenant_id(payload.tenant_id)
    account = _get_account(db, tenant_id, payload.email)
    if not account:
        return AuthForgotPasswordResponse(ok=True)
    raw_token = new_token()
    db.add(
        models.AuthPasswordReset(
            tenant_id=tenant_id,
            user_id=account.user_id,
            token_hash=stable_hash(raw_token),
            expires_at=now_utc() + timedelta(minutes=settings.AUTH_PASSWORD_RESET_TTL_MINUTES),
        )
    )
    db.commit()
    return AuthForgotPasswordResponse(
        ok=True,
        reset_token=raw_token if settings.AUTH_DEV_ECHO_CODES else None,
    )


@router.post("/mfa/challenge", response_model=AuthMfaChallengeResponse)
def mfa_challenge(
    payload: AuthMfaChallengeRequest, db: Session = Depends(get_db)
) -> AuthMfaChallengeResponse:
    tenant_id = validate_tenant_id(payload.tenant_id)
    account = _get_account(db, tenant_id, payload.email)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    code = new_numeric_code(6)
    challenge = models.AuthMfaChallenge(
        tenant_id=tenant_id,
        user_id=account.user_id,
        purpose=payload.purpose,
        code_hash=stable_hash(code),
        expires_at=now_utc() + timedelta(minutes=settings.AUTH_MFA_CODE_TTL_MINUTES),
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return AuthMfaChallengeResponse(
        challenge_id=challenge.id,
        expires_in_seconds=int(settings.AUTH_MFA_CODE_TTL_MINUTES) * 60,
        code=code if settings.AUTH_DEV_ECHO_CODES else None,
    )


@router.post("/mfa/verify", response_model=AuthMfaVerifyResponse)
def mfa_verify(payload: AuthMfaVerifyRequest, db: Session = Depends(get_db)) -> AuthMfaVerifyResponse:
    tenant_id = validate_tenant_id(payload.tenant_id)
    challenge = (
        db.query(models.AuthMfaChallenge)
        .filter(
            models.AuthMfaChallenge.tenant_id == tenant_id,
            models.AuthMfaChallenge.id == payload.challenge_id,
        )
        .first()
    )
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if challenge.verified_at is not None:
        return AuthMfaVerifyResponse(ok=True)
    if _is_expired(challenge.expires_at):
        raise HTTPException(status_code=400, detail="MFA challenge expired")
    if challenge.attempts >= settings.AUTH_MFA_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="MFA challenge max attempts exceeded")
    if challenge.code_hash != stable_hash(payload.code):
        challenge.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    challenge.verified_at = now_utc()
    db.commit()
    return AuthMfaVerifyResponse(ok=True)


@router.post("/reset-password", response_model=AuthGenericResponse)
def reset_password(
    payload: AuthResetPasswordRequest, db: Session = Depends(get_db)
) -> AuthGenericResponse:
    tenant_id = validate_tenant_id(payload.tenant_id)
    account = _get_account(db, tenant_id, payload.email)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    reset = (
        db.query(models.AuthPasswordReset)
        .filter(
            models.AuthPasswordReset.tenant_id == tenant_id,
            models.AuthPasswordReset.user_id == account.user_id,
            models.AuthPasswordReset.token_hash == stable_hash(payload.reset_token),
            models.AuthPasswordReset.consumed_at.is_(None),
        )
        .order_by(models.AuthPasswordReset.id.desc())
        .first()
    )
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    if _is_expired(reset.expires_at):
        raise HTTPException(status_code=400, detail="Reset token expired")

    challenge = (
        db.query(models.AuthMfaChallenge)
        .filter(
            models.AuthMfaChallenge.tenant_id == tenant_id,
            models.AuthMfaChallenge.id == payload.mfa_challenge_id,
            models.AuthMfaChallenge.user_id == account.user_id,
        )
        .first()
    )
    if not challenge or challenge.verified_at is None:
        raise HTTPException(status_code=400, detail="MFA verification required")
    if _is_expired(challenge.expires_at):
        raise HTTPException(status_code=400, detail="MFA challenge expired")

    account.password_hash = hash_password(payload.new_password)
    account.updated_at = now_utc()
    reset.consumed_at = now_utc()
    db.commit()
    return AuthGenericResponse(ok=True)
