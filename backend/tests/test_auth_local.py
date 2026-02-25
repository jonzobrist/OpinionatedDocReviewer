from app.core.config import settings


def test_local_auth_register_verify_login_and_reset_flow(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "local")
    monkeypatch.setattr(settings, "AUTH_DEV_ECHO_CODES", True)
    monkeypatch.setattr(settings, "LOCAL_AUTH_JWT_SECRET", "unit-test-secret")

    register_resp = client.post(
        "/api/auth/register",
        json={
            "tenant_id": "tenant-local",
            "email": "member@example.com",
            "name": "Member",
            "password": "Passw0rd!123",
            "role": "reviewer",
        },
    )
    assert register_resp.status_code == 201
    register_payload = register_resp.json()
    verification_token = register_payload["verification_token"]
    assert verification_token

    preverify_login = client.post(
        "/api/auth/login",
        json={
            "tenant_id": "tenant-local",
            "email": "member@example.com",
            "password": "Passw0rd!123",
        },
    )
    assert preverify_login.status_code == 403

    verify_resp = client.post(
        "/api/auth/verify-email",
        json={
            "tenant_id": "tenant-local",
            "email": "member@example.com",
            "token": verification_token,
        },
    )
    assert verify_resp.status_code == 200

    login_resp = client.post(
        "/api/auth/login",
        json={
            "tenant_id": "tenant-local",
            "email": "member@example.com",
            "password": "Passw0rd!123",
        },
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token

    forbidden_admin = client.get(
        "/api/admin/overview",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert forbidden_admin.status_code == 403

    forgot_resp = client.post(
        "/api/auth/forgot-password",
        json={"tenant_id": "tenant-local", "email": "member@example.com"},
    )
    assert forgot_resp.status_code == 200
    reset_token = forgot_resp.json()["reset_token"]
    assert reset_token

    challenge_resp = client.post(
        "/api/auth/mfa/challenge",
        json={
            "tenant_id": "tenant-local",
            "email": "member@example.com",
            "purpose": "password_reset",
        },
    )
    assert challenge_resp.status_code == 200
    challenge_payload = challenge_resp.json()
    challenge_id = challenge_payload["challenge_id"]
    code = challenge_payload["code"]
    assert code

    verify_mfa = client.post(
        "/api/auth/mfa/verify",
        json={
            "tenant_id": "tenant-local",
            "challenge_id": challenge_id,
            "code": code,
        },
    )
    assert verify_mfa.status_code == 200

    reset_resp = client.post(
        "/api/auth/reset-password",
        json={
            "tenant_id": "tenant-local",
            "email": "member@example.com",
            "reset_token": reset_token,
            "new_password": "N3wPassw0rd!456",
            "mfa_challenge_id": challenge_id,
        },
    )
    assert reset_resp.status_code == 200

    relogin = client.post(
        "/api/auth/login",
        json={
            "tenant_id": "tenant-local",
            "email": "member@example.com",
            "password": "N3wPassw0rd!456",
        },
    )
    assert relogin.status_code == 200


def test_local_auth_allows_project_admin_on_admin_routes(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "local")
    monkeypatch.setattr(settings, "AUTH_DEV_ECHO_CODES", True)
    monkeypatch.setattr(settings, "LOCAL_AUTH_JWT_SECRET", "unit-test-secret")

    register = client.post(
        "/api/auth/register",
        json={
            "tenant_id": "tenant-admin",
            "email": "project-admin@example.com",
            "name": "Project Admin",
            "password": "Passw0rd!123",
            "role": "project_admin",
        },
    )
    token = register.json()["verification_token"]
    client.post(
        "/api/auth/verify-email",
        json={
            "tenant_id": "tenant-admin",
            "email": "project-admin@example.com",
            "token": token,
        },
    )
    login = client.post(
        "/api/auth/login",
        json={
            "tenant_id": "tenant-admin",
            "email": "project-admin@example.com",
            "password": "Passw0rd!123",
        },
    )
    access_token = login.json()["access_token"]
    admin_overview = client.get(
        "/api/admin/overview",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert admin_overview.status_code == 200
