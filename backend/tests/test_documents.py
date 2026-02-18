from app.core.config import settings


def test_document_and_versions_crud(client) -> None:
    headers = {"X-Tenant-Id": "tenant-a"}

    doc_payload = {"title": "Product Requirements v1"}
    create_doc = client.post("/api/documents", json=doc_payload, headers=headers)
    assert create_doc.status_code == 201
    document = create_doc.json()

    list_docs = client.get("/api/documents", headers=headers)
    assert list_docs.status_code == 200
    assert len(list_docs.json()) == 1

    doc_id = document["id"]
    get_doc = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert get_doc.status_code == 200
    assert get_doc.json()["title"] == "Product Requirements v1"

    patch_doc = client.patch(
        f"/api/documents/{doc_id}", json={"title": "PRD v2"}, headers=headers
    )
    assert patch_doc.status_code == 200
    assert patch_doc.json()["title"] == "PRD v2"

    version_payload = {"version_label": "v1", "content": "Initial content"}
    create_version = client.post(
        f"/api/documents/{doc_id}/versions",
        json=version_payload,
        headers=headers,
    )
    assert create_version.status_code == 201
    version = create_version.json()

    library_resp = client.get("/api/documents/library", headers=headers)
    assert library_resp.status_code == 200
    library_items = library_resp.json()
    assert len(library_items) == 1
    entry = library_items[0]
    assert entry["latest_version_id"] == version["id"]
    assert entry["needs_review"] is True
    assert entry["is_archived"] is False

    list_versions = client.get(f"/api/documents/{doc_id}/versions", headers=headers)
    assert list_versions.status_code == 200
    assert len(list_versions.json()) == 1

    archive_resp = client.post(
        f"/api/documents/{doc_id}/archive",
        json={"archived": True},
        headers=headers,
    )
    assert archive_resp.status_code == 200
    assert archive_resp.json()["is_archived"] is True

    list_docs_after_archive = client.get("/api/documents", headers=headers)
    assert list_docs_after_archive.status_code == 200
    assert len(list_docs_after_archive.json()) == 0

    archived_library_resp = client.get("/api/documents/library", headers=headers)
    assert archived_library_resp.status_code == 200
    assert len(archived_library_resp.json()) == 1
    assert archived_library_resp.json()[0]["is_archived"] is True

    restore_resp = client.post(f"/api/documents/{doc_id}/restore", headers=headers)
    assert restore_resp.status_code == 200
    assert restore_resp.json()["is_archived"] is False

    version_id = version["id"]
    get_version = client.get(f"/api/documents/versions/{version_id}", headers=headers)
    assert get_version.status_code == 200
    assert get_version.json()["version_label"] == "v1"

    delete_doc = client.delete(f"/api/documents/{doc_id}", headers=headers)
    assert delete_doc.status_code == 204

    get_missing = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert get_missing.status_code == 404


def test_document_version_content_size_limit(client) -> None:
    headers = {"X-Tenant-Id": "tenant-limit"}
    doc = client.post("/api/documents", json={"title": "Small doc"}, headers=headers).json()
    oversize = "x" * (settings.DOC_MAX_CHARS + 1)
    response = client.post(
        f"/api/documents/{doc['id']}/versions",
        json={"version_label": "v1", "content": oversize},
        headers=headers,
    )
    assert response.status_code == 422
