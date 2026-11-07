import pytest

ADMIN = {"X-Tenant-Id": "meta-permissions"}


def setup_document(client):
    doc = client.post("/api/documents", headers=ADMIN, json={"title": "Restricted"}).json()
    version = client.post(f"/api/documents/{doc['id']}/versions", headers=ADMIN, json={"version_label": "v1", "content": "Private content"}).json()
    user = client.post("/api/admin/users", headers=ADMIN, json={"name": "Reader", "email": "reader@example.com", "role": "reader", "is_active": True}).json()
    return doc["id"], version["id"], user["id"]


def assert_meta_access(client, headers, version_id, read_status, write_status):
    for include in (True, False):
        response = client.get("/api/meta-reviews/latest", headers=headers, params={"document_version_id": version_id, "include_comments": str(include).lower()})
        assert response.status_code == read_status, response.text
    for path in ("/api/meta-reviews", "/api/meta-reviews/ensure"):
        for force in (False, True):
            response = client.post(path, headers=headers, json={"document_version_id": version_id, "force": force})
            assert response.status_code == write_status, response.text


def test_ungranted_user_cannot_read_or_generate_meta_reviews(client, monkeypatch):
    _, version_id, _ = setup_document(client)
    def unexpected_call(**kwargs):
        pytest.fail("Unauthorized request reached synthesis")
    monkeypatch.setattr("app.api.meta_reviews.run_meta_review", unexpected_call)
    monkeypatch.setattr("app.api.meta_reviews.ensure_meta_review_run", unexpected_call)
    assert_meta_access(client, {**ADMIN, "X-User-Email": "reader@example.com"}, version_id, 403, 403)


def test_meta_review_permissions_allow_viewer_reads_and_editor_generation(client, monkeypatch):
    doc_id, version_id, user_id = setup_document(client)
    persona = client.post("/api/personas", headers=ADMIN, json={"name": "Reviewer", "system_prompt": "Review"}).json()
    comment = client.post("/api/comments", headers=ADMIN, json={"document_version_id": version_id, "persona_id": persona["id"], "text": "Clarify this.", "start_offset": 0, "end_offset": 7, "excerpt": "Private"})
    assert comment.status_code == 201
    monkeypatch.setattr("app.reviews.meta_reviewer.synthesize_group", lambda *args, **kwargs: ([], True))
    created = client.post("/api/meta-reviews", headers=ADMIN, json={"document_version_id": version_id})
    assert created.status_code == 201, created.text
    permission = client.post("/api/admin/permissions", headers=ADMIN, json={"document_id": doc_id, "user_id": user_id, "permission_level": "viewer"})
    assert permission.status_code == 201
    headers = {**ADMIN, "X-User-Email": "reader@example.com"}
    assert_meta_access(client, headers, version_id, 200, 403)
    assert client.patch(f"/api/admin/permissions/{permission.json()['id']}", headers=ADMIN, json={"permission_level": "editor"}).status_code == 200
    assert client.post("/api/meta-reviews", headers=headers, json={"document_version_id": version_id}).status_code == 201
    assert client.post("/api/meta-reviews/ensure", headers=headers, json={"document_version_id": version_id}).status_code == 200
    policy = client.post("/api/admin/policies", headers=ADMIN, json={"name": "Deny reader", "effect": "deny", "action": "*", "resource_type": "document", "conditions": {"roles_any": ["reader"]}, "is_active": True})
    assert policy.status_code == 201
    assert_meta_access(client, headers, version_id, 403, 403)


def test_cross_tenant_and_missing_versions_do_not_expose_meta_reviews(client):
    _, version_id, _ = setup_document(client)
    assert_meta_access(client, {"X-Tenant-Id": "other-meta-tenant"}, version_id, 404, 404)
    assert_meta_access(client, ADMIN, version_id + 1000, 404, 404)
