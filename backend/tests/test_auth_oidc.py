from app.core.config import settings


def test_oidc_requires_bearer_for_api_access(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(settings, "OIDC_ALLOW_LOCAL_HEADER_FALLBACK", False)
    resp = client.get("/api/documents")
    assert resp.status_code == 401
    assert "bearer token" in resp.json()["detail"].lower()


def test_oidc_allows_local_header_fallback(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(settings, "OIDC_ALLOW_LOCAL_HEADER_FALLBACK", True)
    resp = client.get("/api/documents", headers={"X-Tenant-Id": "local-dev"})
    assert resp.status_code == 200


def test_oidc_claims_create_user_and_scope_tenant(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(settings, "OIDC_TENANT_CLAIM", "tid")
    monkeypatch.setattr(settings, "OIDC_EMAIL_CLAIM", "email")
    monkeypatch.setattr(
        "app.api.deps.decode_access_token",
        lambda _: {
            "sub": "user-123",
            "email": "member@example.com",
            "name": "Member User",
            "tid": "tenant-oidc",
            "roles": ["member"],
        },
    )
    resp = client.get("/api/documents", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_oidc_admin_role_can_access_admin_endpoints(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(settings, "OIDC_TENANT_CLAIM", "tid")
    monkeypatch.setattr(settings, "OIDC_EMAIL_CLAIM", "email")
    monkeypatch.setattr(settings, "OIDC_ROLES_CLAIM", "roles")
    monkeypatch.setattr(settings, "OIDC_ADMIN_ROLE", "admin")
    monkeypatch.setattr(
        "app.api.deps.decode_access_token",
        lambda _: {
            "sub": "admin-123",
            "email": "admin@example.com",
            "name": "Admin User",
            "tid": "tenant-oidc-admin",
            "roles": ["admin"],
        },
    )
    resp = client.get("/api/admin/overview", headers={"Authorization": "Bearer test-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_id"] == "tenant-oidc-admin"
