from fastapi import HTTPException

from app.core.config import settings
from app.reviews.git_repo import ensure_repo


def test_invalid_tenant_header_rejected(client) -> None:
    response = client.get("/api/documents", headers={"X-Tenant-Id": "../escape"})
    assert response.status_code == 400
    assert "Invalid tenant id" in response.json()["detail"]


def test_git_repo_rejects_path_traversal_tenant() -> None:
    try:
        ensure_repo("../escape", 1)
        raise AssertionError("Expected HTTPException for invalid tenant id")
    except HTTPException as exc:
        assert exc.status_code == 400


def test_rate_limit_blocks_excess_requests(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "RATE_LIMIT_MAX_REQUESTS", 1)
    first = client.get("/api/status")
    second = client.get("/api/status")
    assert first.status_code == 200
    assert second.status_code == 429


def test_csrf_origin_guard_blocks_untrusted_origin(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "CSRF_ENFORCE_ORIGIN", True)
    monkeypatch.setattr(settings, "CORS_ALLOW_ORIGINS", "https://allowed.example")
    headers = {
        "X-Tenant-Id": "tenant-csrf",
        "Origin": "https://evil.example",
    }
    response = client.post("/api/documents", json={"title": "Doc"}, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Origin not allowed"
