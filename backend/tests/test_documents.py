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


def test_import_review_bundle_restores_comments_and_meta(client) -> None:
    headers = {"X-Tenant-Id": "tenant-import"}
    bundle_payload = {
        "schema_version": "odr.review-bundle.v2",
        "document": {"title": "Imported Bundle Doc"},
        "version": {"version_label": "Imported v1", "content": "Alpha beta gamma delta"},
        "review_job": {
            "status": "completed",
            "trigger": "import",
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
        "personas": [
            {
                "id": 99,
                "name": "Bundle Persona",
                "description": "from bundle",
                "system_prompt": "review",
                "focus_areas": ["clarity"],
                "tone": "direct",
                "output_requirements": {"format": "bullet_list"},
                "examples": [],
                "sort_order": 10,
                "color_theme": "#1d8a7a",
                "is_active": True,
            }
        ],
        "comments": [
            {
                "id": 1001,
                "persona_id": 99,
                "persona_name": "Bundle Persona",
                "text": "Clarify opening",
                "start_offset": 0,
                "end_offset": 5,
                "excerpt": "Alpha",
                "output_metadata": {"severity": "low"},
            }
        ],
        "meta_review_run": {
            "status": "completed",
            "is_synthesized": True,
            "provider": "openai",
            "model": "gpt-4o-mini",
            "comments": [
                {
                    "content": "Tighten intro",
                    "category": "clarity",
                    "priority": "medium",
                    "start_offset": 0,
                    "end_offset": 5,
                    "order_index": 0,
                    "is_unsynthesized": False,
                    "sources": [
                        {
                            "comment_id": 1001,
                            "reviewer_name": "Bundle Persona",
                            "reviewer_id": 99,
                            "original_comment_text": "Clarify opening",
                        }
                    ],
                }
            ],
        },
    }

    import_resp = client.post("/api/documents/import-bundle", json=bundle_payload, headers=headers)
    assert import_resp.status_code == 201
    result = import_resp.json()
    assert result["comments_imported"] == 1
    assert result["meta_comments_imported"] == 1

    library_resp = client.get("/api/documents/library", headers=headers)
    assert library_resp.status_code == 200
    assert any(item["id"] == result["document_id"] for item in library_resp.json())

    comments_resp = client.get(
        f"/api/comments?document_version_id={result['version_id']}&review_job_id={result['review_job_id']}",
        headers=headers,
    )
    assert comments_resp.status_code == 200
    comments = comments_resp.json()
    assert len(comments) == 1
    assert comments[0]["text"] == "Clarify opening"

    meta_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={result['version_id']}&review_job_id={result['review_job_id']}",
        headers=headers,
    )
    assert meta_resp.status_code == 200
    meta = meta_resp.json()
    assert len(meta["comments"]) == 1
    assert meta["comments"][0]["sources"][0]["reviewer_name"] == "Bundle Persona"
