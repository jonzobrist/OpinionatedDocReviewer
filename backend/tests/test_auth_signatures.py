"""Exercise the locked JWT/crypto/JWKS stack without contacting an identity provider."""

import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.error import URLError

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from app.auth import local_auth, oidc
from app.core.config import settings


@pytest.fixture()
def signed_oidc(monkeypatch):
    issuer = "https://identity.example.test"
    jwks_url = f"{issuer}/.well-known/jwks.json"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    public_jwk.update(kid="current-key", use="sig", alg="RS256")
    requests = []

    def open_jwks(_opener, request, *, timeout):
        assert request.full_url == jwks_url
        assert timeout > 0
        requests.append(request.full_url)
        return io.BytesIO(json.dumps({"keys": [public_jwk]}).encode())

    # Only replace the network boundary. Parsing, key selection, caching,
    # signature verification, and claims validation use the real libraries.
    monkeypatch.setattr(jwt.jwks_client.urllib.request.OpenerDirector, "open", open_jwks)
    monkeypatch.setattr(settings, "OIDC_ISSUER_URL", issuer)
    monkeypatch.setattr(settings, "OIDC_JWKS_URL", "")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "odr-api")
    monkeypatch.setattr(settings, "OIDC_ALGORITHMS", "RS256")
    oidc._jwks_client.cache_clear()
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {
        "sub": "signed-user",
        "iss": issuer,
        "aud": "odr-api",
        "iat": now - 10,
        "exp": now + 300,
        "tid": "signed-tenant",
        "email": "signed@example.com",
        "roles": ["member"],
    }

    def encode(overrides=None, *, signing_key=key, algorithm="RS256", kid="current-key"):
        return jwt.encode(
            {**claims, **(overrides or {})},
            signing_key,
            algorithm=algorithm,
            headers={"kid": kid},
        )

    yield SimpleNamespace(encode=encode, claims=claims, requests=requests, jwks_url=jwks_url)
    oidc._jwks_client.cache_clear()


def test_oidc_real_signature_and_jwks_cache(signed_oidc) -> None:
    token = signed_oidc.encode()
    assert oidc.decode_access_token(token) == signed_oidc.claims
    assert oidc.decode_access_token(token) == signed_oidc.claims
    assert signed_oidc.requests == [signed_oidc.jwks_url]


def test_oidc_signed_token_reaches_tenant_scoped_api(client, monkeypatch, signed_oidc) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(settings, "OIDC_TENANT_CLAIM", "tid")
    monkeypatch.setattr(settings, "OIDC_EMAIL_CLAIM", "email")
    response = client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {signed_oidc.encode()}"},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "claims",
    [
        {"exp": 1},
        {"iss": "https://untrusted.example.test"},
        {"aud": "another-api"},
        {"nbf": 4102444800},
    ],
    ids=["expired", "wrong-issuer", "wrong-audience", "not-yet-valid"],
)
def test_oidc_rejects_invalid_signed_claims(signed_oidc, claims) -> None:
    with pytest.raises(HTTPException) as exc:
        oidc.decode_access_token(signed_oidc.encode(claims))
    assert exc.value.status_code == 401


def test_oidc_rejects_forged_signature(signed_oidc) -> None:
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(HTTPException) as exc:
        oidc.decode_access_token(signed_oidc.encode(signing_key=attacker_key))
    assert exc.value.status_code == 401


def test_oidc_rejects_disallowed_algorithm(signed_oidc) -> None:
    with pytest.raises(HTTPException) as exc:
        oidc.decode_access_token(signed_oidc.encode(algorithm="RS512"))
    assert exc.value.status_code == 401


def test_oidc_unknown_kid_does_not_refresh_on_every_request(signed_oidc) -> None:
    oidc.decode_access_token(signed_oidc.encode())
    for _ in range(3):
        with pytest.raises(HTTPException) as exc:
            oidc.decode_access_token(signed_oidc.encode(kid="unknown-key"))
        assert exc.value.status_code == 401
    assert signed_oidc.requests == [signed_oidc.jwks_url]


def test_oidc_fetch_failure_preserves_cached_keys(signed_oidc, monkeypatch) -> None:
    token = signed_oidc.encode()
    oidc.decode_access_token(token)

    def unavailable(*args, **kwargs):
        raise URLError("temporary identity provider outage")

    monkeypatch.setattr(jwt.jwks_client.urllib.request.OpenerDirector, "open", unavailable)
    with pytest.raises(jwt.PyJWKClientConnectionError):
        oidc._jwks_client(signed_oidc.jwks_url).fetch_data()
    assert oidc.decode_access_token(token) == signed_oidc.claims


@pytest.mark.parametrize("decode", [jwt.decode, jwt.decode_complete])
def test_unverified_decode_does_not_disable_later_claim_validation(decode) -> None:
    """Regression for GHSA-gvp8-978c-rx2q: caller options must stay unchanged."""
    secret = "unit-test-secret-at-least-32-bytes"
    token = jwt.encode({"exp": 1}, secret, algorithm="HS256")
    options = {"verify_signature": False}
    decode(token, options=options)
    assert options == {"verify_signature": False}
    options["verify_signature"] = True
    with pytest.raises(jwt.ExpiredSignatureError):
        decode(token, secret, algorithms=["HS256"], options=options)


def test_local_auth_real_signature_and_rejection(monkeypatch) -> None:
    secret = "unit-test-secret-at-least-32-bytes"
    monkeypatch.setattr(settings, "LOCAL_AUTH_JWT_SECRET", secret)
    monkeypatch.setattr(settings, "LOCAL_AUTH_JWT_ALGORITHM", "HS256")
    token = local_auth.issue_access_token(
        tenant_id="local-tenant", user_id=42, email="member@example.com", role="member"
    )
    assert local_auth.decode_access_token(token)["sub"] == "42"
    for payload, signing_key in [
        ({"iss": "odr-local-auth", "exp": 1}, secret),
        ({"iss": "wrong-issuer"}, secret),
        ({"iss": "odr-local-auth"}, "another-secret-at-least-32-bytes-long"),
    ]:
        with pytest.raises(HTTPException) as exc:
            local_auth.decode_access_token(jwt.encode(payload, signing_key, algorithm="HS256"))
        assert exc.value.status_code == 401
