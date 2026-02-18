from __future__ import annotations

from functools import lru_cache

import jwt
from fastapi import HTTPException

from app.core.config import settings


@lru_cache(maxsize=8)
def _jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(jwks_url)


def decode_access_token(token: str) -> dict:
    issuer = (settings.OIDC_ISSUER_URL or "").strip()
    if not issuer:
        raise HTTPException(status_code=500, detail="OIDC_ISSUER_URL is not configured")
    jwks_url = (settings.OIDC_JWKS_URL or "").strip() or f"{issuer.rstrip('/')}/.well-known/jwks.json"
    audience = (settings.OIDC_AUDIENCE or "").strip()
    algorithms = [item.strip() for item in settings.OIDC_ALGORITHMS.split(",") if item.strip()]
    if not algorithms:
        algorithms = ["RS256"]

    try:
        signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        options = {"verify_aud": bool(audience)}
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=algorithms,
            audience=audience or None,
            issuer=issuer,
            options=options,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid bearer token: {exc}") from exc
