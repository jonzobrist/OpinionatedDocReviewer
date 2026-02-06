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

    list_versions = client.get(f"/api/documents/{doc_id}/versions", headers=headers)
    assert list_versions.status_code == 200
    assert len(list_versions.json()) == 1

    version_id = version["id"]
    get_version = client.get(f"/api/documents/versions/{version_id}", headers=headers)
    assert get_version.status_code == 200
    assert get_version.json()["version_label"] == "v1"

    delete_doc = client.delete(f"/api/documents/{doc_id}", headers=headers)
    assert delete_doc.status_code == 204

    get_missing = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert get_missing.status_code == 404
