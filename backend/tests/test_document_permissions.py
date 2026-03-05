from app.reviews.quality_telemetry import build_empty_review_quality_telemetry


def _assert_quality_telemetry_contract(payload: dict) -> None:
    expected = build_empty_review_quality_telemetry()
    assert payload["total_comments"] >= 0
    assert payload["fallback_count"] >= 0
    assert payload["truncated_count"] >= 0
    assert set(expected["violation_count_by_type"]).issubset(payload["violation_count_by_type"].keys())
    assert isinstance(payload["per_persona"], dict)


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
    can_review_data = can_review.json()
    _assert_quality_telemetry_contract(can_review_data["quality_telemetry"])

    hidden_doc = client.post("/api/documents", json={"title": "Admin Only"}, headers=admin_headers)
    assert hidden_doc.status_code == 201
    hidden_doc_id = hidden_doc.json()["id"]
    hidden_version = client.post(
        f"/api/documents/{hidden_doc_id}/versions",
        json={"version_label": "v1", "content": "hidden content"},
        headers=admin_headers,
    )
    assert hidden_version.status_code == 201
    hidden_version_id = hidden_version.json()["id"]

    hidden_job = client.post(
        "/api/review-jobs",
        json={"document_version_id": hidden_version_id},
        headers=admin_headers,
    )
    assert hidden_job.status_code == 201

    viewer_jobs = client.get("/api/review-jobs", headers=viewer_headers)
    assert viewer_jobs.status_code == 200
    jobs_payload = viewer_jobs.json()
    assert [job["id"] for job in jobs_payload] == [can_review_data["id"]]
    for job in jobs_payload:
        _assert_quality_telemetry_contract(job["quality_telemetry"])


def test_review_job_reads_are_tenant_scoped_for_non_admin_users(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.review_jobs.enqueue_review_job", lambda job_id, tenant_id: None)

    tenant_a = "tenant-review-scope-a"
    tenant_b = "tenant-review-scope-b"

    admin_a_headers = {"X-Tenant-Id": tenant_a, "X-User-Email": f"admin+{tenant_a}@local"}
    admin_b_headers = {"X-Tenant-Id": tenant_b, "X-User-Email": f"admin+{tenant_b}@local"}

    create_viewer = client.post(
        "/api/admin/users",
        json={
            "name": "Scope Viewer",
            "email": "scope-viewer@example.com",
            "role": "default",
            "is_active": True,
        },
        headers=admin_a_headers,
    )
    assert create_viewer.status_code == 201
    viewer_id = create_viewer.json()["id"]
    viewer_headers = {"X-Tenant-Id": tenant_a, "X-User-Email": "scope-viewer@example.com"}

    doc_a = client.post("/api/documents", json={"title": "Tenant A"}, headers=admin_a_headers)
    assert doc_a.status_code == 201
    doc_a_id = doc_a.json()["id"]
    version_a = client.post(
        f"/api/documents/{doc_a_id}/versions",
        json={"version_label": "v1", "content": "content a"},
        headers=admin_a_headers,
    )
    assert version_a.status_code == 201
    version_a_id = version_a.json()["id"]

    grant_viewer = client.post(
        "/api/admin/permissions",
        json={"document_id": doc_a_id, "user_id": viewer_id, "permission_level": "viewer"},
        headers=admin_a_headers,
    )
    assert grant_viewer.status_code == 201

    job_a = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_a_id},
        headers=admin_a_headers,
    )
    assert job_a.status_code == 201
    job_a_id = job_a.json()["id"]

    doc_b = client.post("/api/documents", json={"title": "Tenant B"}, headers=admin_b_headers)
    assert doc_b.status_code == 201
    doc_b_id = doc_b.json()["id"]
    version_b = client.post(
        f"/api/documents/{doc_b_id}/versions",
        json={"version_label": "v1", "content": "content b"},
        headers=admin_b_headers,
    )
    assert version_b.status_code == 201
    version_b_id = version_b.json()["id"]

    job_b = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_b_id},
        headers=admin_b_headers,
    )
    assert job_b.status_code == 201
    job_b_id = job_b.json()["id"]

    viewer_jobs = client.get("/api/review-jobs", headers=viewer_headers)
    assert viewer_jobs.status_code == 200
    jobs_payload = viewer_jobs.json()

    assert len(jobs_payload) == 1
    assert jobs_payload[0]["id"] == job_a_id
    assert jobs_payload[0]["tenant_id"] == tenant_a
    assert jobs_payload[0]["id"] != job_b_id
    _assert_quality_telemetry_contract(jobs_payload[0]["quality_telemetry"])
