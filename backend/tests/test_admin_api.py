def test_admin_overview_and_user_permission_crud(client) -> None:
    headers = {"X-Tenant-Id": "tenant-admin"}

    doc_resp = client.post("/api/documents", json={"title": "Policy"}, headers=headers)
    assert doc_resp.status_code == 201
    document_id = doc_resp.json()["id"]

    version_resp = client.post(
        f"/api/documents/{document_id}/versions",
        json={"version_label": "v1", "content": "hello world"},
        headers=headers,
    )
    assert version_resp.status_code == 201
    version_id = version_resp.json()["id"]

    job_resp = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_id, "trigger": "manual"},
        headers=headers,
    )
    assert job_resp.status_code == 201

    overview = client.get("/api/admin/overview", headers=headers)
    assert overview.status_code == 200
    overview_body = overview.json()
    assert "repository" in overview_body
    assert "users" in overview_body
    assert "jobs" in overview_body

    users_resp = client.get("/api/admin/users", headers=headers)
    assert users_resp.status_code == 200
    users = users_resp.json()
    assert len(users) >= 1

    created_user_resp = client.post(
        "/api/admin/users",
        json={
            "name": "Reviewer",
            "email": "reviewer@example.com",
            "role": "default",
            "is_active": True,
        },
        headers=headers,
    )
    assert created_user_resp.status_code == 201
    user_id = created_user_resp.json()["id"]

    updated_user_resp = client.patch(
        f"/api/admin/users/{user_id}",
        json={"role": "admin"},
        headers=headers,
    )
    assert updated_user_resp.status_code == 200
    assert updated_user_resp.json()["role"] == "admin"

    perm_resp = client.post(
        "/api/admin/permissions",
        json={
            "document_id": document_id,
            "user_id": user_id,
            "permission_level": "editor",
        },
        headers=headers,
    )
    assert perm_resp.status_code == 201
    perm_id = perm_resp.json()["id"]

    list_perm_resp = client.get(
        f"/api/admin/permissions?document_id={document_id}",
        headers=headers,
    )
    assert list_perm_resp.status_code == 200
    assert len(list_perm_resp.json()) >= 1

    patch_perm_resp = client.patch(
        f"/api/admin/permissions/{perm_id}",
        json={"permission_level": "viewer"},
        headers=headers,
    )
    assert patch_perm_resp.status_code == 200
    assert patch_perm_resp.json()["permission_level"] == "viewer"

    delete_perm_resp = client.delete(f"/api/admin/permissions/{perm_id}", headers=headers)
    assert delete_perm_resp.status_code == 204

    delete_user_resp = client.delete(f"/api/admin/users/{user_id}", headers=headers)
    assert delete_user_resp.status_code == 204
