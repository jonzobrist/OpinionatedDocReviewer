from fastapi import Request
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app


def test_allowed_hosts_can_restrict_to_specific_hostname(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", "odr.zlyxy.me")
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    app = create_app(init_db_on_startup=False)
    client = TestClient(app)

    allowed = client.get("/api/health", headers={"host": "odr.zlyxy.me"})
    blocked = client.get("/api/health", headers={"host": "evil.example"})

    assert allowed.status_code == 200
    assert blocked.status_code == 400
    assert "invalid host header" in blocked.text.lower()


def test_allowed_hosts_supports_wildcard_matching(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", "*.zlyxy.me,zlyxy.me")
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", False)
    app = create_app(init_db_on_startup=False)
    client = TestClient(app)

    wildcard = client.get("/api/health", headers={"host": "odr.zlyxy.me"})
    apex = client.get("/api/health", headers={"host": "zlyxy.me"})
    blocked = client.get("/api/health", headers={"host": "odr.other.me"})

    assert wildcard.status_code == 200
    assert apex.status_code == 200
    assert blocked.status_code == 400


def test_proxy_headers_can_enable_tls_offload_scheme(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", "*")
    monkeypatch.setattr(settings, "TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "PROXY_TRUSTED_IPS", "*")
    app = create_app(init_db_on_startup=False)

    @app.get("/_probe/scheme")
    def probe(request: Request) -> dict:
        return {"scheme": request.url.scheme}

    client = TestClient(app)
    response = client.get(
        "/_probe/scheme",
        headers={
            "x-forwarded-for": "203.0.113.10",
            "x-forwarded-proto": "https",
        },
    )

    assert response.status_code == 200
    assert response.json()["scheme"] == "https"
