import pytest


ADMIN = {"X-Tenant-Id": "persona-security"}
PERSONA = {"name": "Reviewer", "system_prompt": "Review carefully."}


def create_user(client, role):
    email = f"{role}@example.com"
    response = client.post(
        "/api/admin/users",
        headers=ADMIN,
        json={"name": role, "email": email, "role": role, "is_active": True},
    )
    assert response.status_code == 201
    return {**ADMIN, "X-User-Email": email}


@pytest.mark.parametrize("role", ["reader", "reviewer", "author", "auditor", "service_account", "default"])
def test_non_admin_cannot_mutate_personas_or_groups(client, role):
    headers = create_user(client, role)
    persona = client.post("/api/personas", headers=ADMIN, json=PERSONA).json()
    group = client.post("/api/persona-groups", headers=ADMIN, json={"name": "Editors"}).json()
    before_personas = client.get("/api/personas", headers=ADMIN).json()
    before_groups = client.get("/api/persona-groups", headers=ADMIN).json()
    operations = [
        ("POST", "/api/personas", PERSONA),
        ("PATCH", f"/api/personas/{persona['id']}", {"name": "Changed"}),
        ("DELETE", f"/api/personas/{persona['id']}", None),
        ("POST", "/api/personas/reset-defaults", None),
        ("POST", f"/api/personas/{persona['id']}/reset-default", None),
        ("POST", "/api/personas/bundle/import", {"personas": [PERSONA]}),
        ("POST", "/api/persona-groups", {"name": "Changed"}),
        ("PATCH", f"/api/persona-groups/{group['id']}", {"name": "Changed"}),
        ("DELETE", f"/api/persona-groups/{group['id']}", None),
    ]
    for method, path, payload in operations:
        response = client.request(method, path, headers=headers, json=payload)
        assert response.status_code == 403, (method, path, response.text)
    assert client.get("/api/personas", headers=headers).json() == before_personas
    assert client.get("/api/persona-groups", headers=headers).json() == before_groups
    assert client.get("/api/personas/bundle/export", headers=headers).status_code == 200


@pytest.mark.parametrize("role", ["admin", "project_admin", "system_admin"])
def test_management_roles_can_manage_personas_and_groups(client, role):
    headers = create_user(client, role)
    group = client.post("/api/persona-groups", headers=headers, json={"name": "Editors"})
    assert group.status_code == 201
    persona = client.post("/api/personas", headers=headers, json={**PERSONA, "group_id": group.json()["id"]})
    assert persona.status_code == 201
    path = f"/api/personas/{persona.json()['id']}"
    assert client.patch(path, headers=headers, json={"tone": "direct"}).status_code == 200
    assert client.delete(path, headers=headers).status_code == 204
    assert client.delete(f"/api/persona-groups/{group.json()['id']}", headers=headers).status_code == 204
    assert client.post("/api/personas/reset-defaults", headers=headers).status_code == 200
    assert client.post("/api/personas/bundle/import", headers=headers, json={"personas": [PERSONA]}).status_code == 200


def test_built_in_flags_cannot_be_forged_or_removed(client):
    for flag in ("is_default", "is_system_locked"):
        assert client.post("/api/personas", headers=ADMIN, json={**PERSONA, flag: True}).status_code == 422
    defaults = client.post("/api/personas/reset-defaults", headers=ADMIN).json()
    path = f"/api/personas/{defaults[0]['id']}"
    for flag in ("is_default", "is_system_locked"):
        assert client.patch(path, headers=ADMIN, json={flag: False}).status_code == 422
    assert client.delete(path, headers=ADMIN).status_code == 409
    # Editing behavior and disabling remain supported, including clients that
    # round-trip unchanged flags when saving a complete editor form.
    response = client.patch(path, headers=ADMIN, json={"tone": "direct", "is_active": False, "is_default": True, "is_system_locked": True})
    assert response.status_code == 200
    assert response.json()["is_system_locked"] is True
    assert response.json()["is_active"] is False
    assert client.post(path + "/reset-default", headers=ADMIN).status_code == 200
    custom = client.post("/api/personas", headers=ADMIN, json=PERSONA).json()
    for flag in ("is_default", "is_system_locked"):
        assert client.patch(f"/api/personas/{custom['id']}", headers=ADMIN, json={flag: True}).status_code == 422


def test_group_assignment_is_tenant_scoped_and_atomic(client):
    foreign = client.post("/api/persona-groups", headers={"X-Tenant-Id": "other-tenant"}, json={"name": "Foreign"}).json()
    for group_id in (foreign["id"], foreign["id"] + 1000):
        assert client.post("/api/personas", headers=ADMIN, json={**PERSONA, "group_id": group_id}).status_code == 404
    persona = client.post("/api/personas", headers=ADMIN, json=PERSONA).json()
    path = f"/api/personas/{persona['id']}"
    assert client.patch(path, headers=ADMIN, json={"name": "Changed", "group_id": foreign["id"]}).status_code == 404
    assert client.get(path, headers=ADMIN).json() == persona
