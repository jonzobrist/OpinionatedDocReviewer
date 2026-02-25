def test_deny_policy_overrides_document_permission_and_logs_decision(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.review_jobs.enqueue_review_job", lambda job_id, tenant_id: None)
    tenant = "tenant-policy"
    admin_headers = {"X-Tenant-Id": tenant, "X-User-Email": f"admin+{tenant}@local"}

    create_user = client.post(
        "/api/admin/users",
        json={
            "name": "External Reviewer",
            "email": "external@example.com",
            "role": "reviewer",
            "tags": ["external"],
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert create_user.status_code == 201
    reviewer_id = create_user.json()["id"]
    reviewer_headers = {"X-Tenant-Id": tenant, "X-User-Email": "external@example.com"}

    create_doc = client.post(
        "/api/documents",
        json={"title": "Confidential Plan", "tags": ["confidential"]},
        headers=admin_headers,
    )
    assert create_doc.status_code == 201
    document_id = create_doc.json()["id"]
    version = client.post(
        f"/api/documents/{document_id}/versions",
        json={"version_label": "v1", "content": "top secret details"},
        headers=admin_headers,
    )
    assert version.status_code == 201
    version_id = version.json()["id"]

    grant = client.post(
        "/api/admin/permissions",
        json={"document_id": document_id, "user_id": reviewer_id, "permission_level": "viewer"},
        headers=admin_headers,
    )
    assert grant.status_code == 201

    deny_policy = client.post(
        "/api/admin/policies",
        json={
            "name": "Deny external on confidential read",
            "effect": "deny",
            "action": "document.read",
            "resource_type": "document",
            "conditions": {
                "user_tags_any": ["external"],
                "document_tags_any": ["confidential"],
            },
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert deny_policy.status_code == 201

    denied_read = client.get(f"/api/documents/{document_id}", headers=reviewer_headers)
    assert denied_read.status_code == 403

    policy_id = deny_policy.json()["id"]
    disable = client.patch(
        f"/api/admin/policies/{policy_id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert disable.status_code == 200

    allowed_read = client.get(f"/api/documents/{document_id}", headers=reviewer_headers)
    assert allowed_read.status_code == 200

    allow_write = client.post(
        "/api/admin/policies",
        json={
            "name": "Allow reviewer write",
            "effect": "allow",
            "action": "document.write",
            "resource_type": "document",
            "conditions": {"roles_any": ["reviewer"], "permission_level": "editor"},
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert allow_write.status_code == 201

    can_review = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_id},
        headers=reviewer_headers,
    )
    assert can_review.status_code == 201

    decisions = client.get("/api/admin/policy-decisions?limit=20", headers=admin_headers)
    assert decisions.status_code == 200
    payload = decisions.json()
    assert len(payload) >= 2
    assert any(item["outcome"] == "denied" for item in payload)
    assert any(item["outcome"] == "allowed" for item in payload)
