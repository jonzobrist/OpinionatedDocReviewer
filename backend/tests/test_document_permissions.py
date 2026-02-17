def test_document_permissions_enforced_for_review_actions(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.review_jobs.enqueue_review_job", lambda job_id, tenant_id: None)
    tenant = "tenant-perms"
    admin_headers = {"X-Tenant-Id": tenant, "X-User-Email": f"admin+{tenant}@local"}

    create_user = client.post(
        "/api/admin/users",
        json={
            "name": "Viewer",
            "email": "viewer@example.com",
            "role": "default",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert create_user.status_code == 201
    viewer_id = create_user.json()["id"]
    viewer_headers = {"X-Tenant-Id": tenant, "X-User-Email": "viewer@example.com"}

    doc_resp = client.post("/api/documents", json={"title": "Sec Doc"}, headers=admin_headers)
    assert doc_resp.status_code == 201
    document_id = doc_resp.json()["id"]
    version_resp = client.post(
        f"/api/documents/{document_id}/versions",
        json={"version_label": "v1", "content": "content"},
        headers=admin_headers,
    )
    assert version_resp.status_code == 201
    version_id = version_resp.json()["id"]

    grant_viewer = client.post(
        "/api/admin/permissions",
        json={"document_id": document_id, "user_id": viewer_id, "permission_level": "viewer"},
        headers=admin_headers,
    )
    assert grant_viewer.status_code == 201

    can_read = client.get(f"/api/documents/{document_id}", headers=viewer_headers)
    assert can_read.status_code == 200

    cannot_review = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_id},
        headers=viewer_headers,
    )
    assert cannot_review.status_code == 403

    set_editor = client.patch(
        f"/api/admin/permissions/{grant_viewer.json()['id']}",
        json={"permission_level": "editor"},
        headers=admin_headers,
    )
    assert set_editor.status_code == 200

    can_review = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_id},
        headers=viewer_headers,
    )
    assert can_review.status_code == 201
