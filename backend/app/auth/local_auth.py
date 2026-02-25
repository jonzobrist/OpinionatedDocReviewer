from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException

from app.core.config import settings

_password_hasher = PasswordHasher()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def issue_access_token(*, tenant_id: str, user_id: int, email: str, role: str) -> str:
    ttl = max(1, int(settings.LOCAL_AUTH_ACCESS_TOKEN_TTL_MINUTES))
    issued_at = now_utc()
    payload = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "email": email,
        "role": role,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(minutes=ttl)).timestamp()),
        "iss": "odr-local-auth",
    }
    return jwt.encode(
        payload,
        settings.LOCAL_AUTH_JWT_SECRET,
        algorithm=settings.LOCAL_AUTH_JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.LOCAL_AUTH_JWT_SECRET,
            algorithms=[settings.LOCAL_AUTH_JWT_ALGORITHM],
            issuer="odr-local-auth",
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid bearer token: {exc}") from exc


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_numeric_code(length: int = 6) -> str:
    upper = 10**length
    return f"{secrets.randbelow(upper):0{length}d}"


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

