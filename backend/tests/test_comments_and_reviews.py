def test_comments_and_review_jobs(client, monkeypatch) -> None:
    def _noop_enqueue(job_id: int, tenant_id: str) -> None:
        return None

    monkeypatch.setattr("app.api.review_jobs.enqueue_review_job", _noop_enqueue)
    headers = {"X-Tenant-Id": "tenant-a"}

    persona_payload = {
        "name": "Risk Analyst",
        "description": "Finds edge cases",
        "system_prompt": "You are a risk analyst.",
        "focus_areas": ["risk"],
        "tone": "calm",
        "is_active": True,
        "group_id": None,
    }
    persona_resp = client.post("/api/personas", json=persona_payload, headers=headers)
    assert persona_resp.status_code == 201
    persona_id = persona_resp.json()["id"]

    doc_payload = {"title": "Security Policy"}
    doc_resp = client.post("/api/documents", json=doc_payload, headers=headers)
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    version_payload = {"version_label": "v1", "content": "Hello world"}
    version_resp = client.post(
        f"/api/documents/{doc_id}/versions",
        json=version_payload,
        headers=headers,
    )
    assert version_resp.status_code == 201
    version_id = version_resp.json()["id"]

    job_resp = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_id},
        headers=headers,
    )
    assert job_resp.status_code == 201
    assert job_resp.json()["status"] == "queued"
    assert job_resp.json()["provider"] in {"openai", "bedrock"}
    assert isinstance(job_resp.json()["model"], str)

    comment_payload = {
        "persona_id": persona_id,
        "document_version_id": version_id,
        "text": "Consider adding more details.",
        "start_offset": 0,
        "end_offset": 5,
        "excerpt": "Hello",
    }
    comment_resp = client.post("/api/comments", json=comment_payload, headers=headers)
    assert comment_resp.status_code == 201

    list_comments = client.get(
        f"/api/comments?document_version_id={version_id}", headers=headers
    )
    assert list_comments.status_code == 200
    assert len(list_comments.json()) == 1


def test_retry_failed_persona_endpoint(client, monkeypatch) -> None:
    def _noop_enqueue(job_id: int, tenant_id: str) -> None:
        return None

    monkeypatch.setattr("app.api.review_jobs.enqueue_review_job", _noop_enqueue)
    monkeypatch.setattr(
        "app.api.review_jobs.retry_failed_persona_in_job",
        lambda review_job_id, tenant_id, persona_id: 2,
    )
    headers = {"X-Tenant-Id": "tenant-retry"}

    persona_resp = client.post(
        "/api/personas",
        json={
            "name": "Retry Persona",
            "description": "retry",
            "system_prompt": "retry",
            "focus_areas": [],
            "tone": "direct",
            "is_active": True,
            "group_id": None,
        },
        headers=headers,
    )
    persona_id = persona_resp.json()["id"]

    doc_resp = client.post("/api/documents", json={"title": "Doc"}, headers=headers)
    doc_id = doc_resp.json()["id"]
    version_resp = client.post(
        f"/api/documents/{doc_id}/versions",
        json={"version_label": "v1", "content": "hello"},
        headers=headers,
    )
    version_id = version_resp.json()["id"]
    job_resp = client.post(
        "/api/review-jobs",
        json={"document_version_id": version_id},
        headers=headers,
    )
    job_id = job_resp.json()["id"]

    retry_resp = client.post(
        f"/api/review-jobs/{job_id}/retry-persona/{persona_id}",
        headers=headers,
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "retried"
