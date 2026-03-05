from app.reviews.parsing import REQUIRED_OUTPUT_METADATA_KEYS, VIOLATION_MISSING_QUOTE_EXCERPT, VIOLATION_TRUNCATED_OUTPUT
from app.reviews.quality_telemetry import build_empty_review_quality_telemetry


def _assert_quality_telemetry_contract(payload: dict) -> None:
    expected = build_empty_review_quality_telemetry()
    assert payload["total_comments"] >= 0
    assert payload["fallback_count"] >= 0
    assert payload["truncated_count"] >= 0
    assert set(expected["violation_count_by_type"]).issubset(payload["violation_count_by_type"].keys())
    assert isinstance(payload["per_persona"], dict)


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
    job_data = job_resp.json()
    assert job_data["status"] == "queued"
    assert job_data["provider"] in {"openai", "bedrock"}
    assert isinstance(job_data["model"], str)
    _assert_quality_telemetry_contract(job_data["quality_telemetry"])

    list_jobs = client.get(f"/api/review-jobs?document_version_id={version_id}", headers=headers)
    assert list_jobs.status_code == 200
    jobs = list_jobs.json()
    assert len(jobs) == 1
    _assert_quality_telemetry_contract(jobs[0]["quality_telemetry"])

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


def test_comments_endpoint_normalizes_legacy_output_metadata(client, monkeypatch) -> None:
    def _noop_enqueue(job_id: int, tenant_id: str) -> None:
        return None

    monkeypatch.setattr("app.api.review_jobs.enqueue_review_job", _noop_enqueue)
    headers = {"X-Tenant-Id": "tenant-legacy-meta"}

    persona_resp = client.post(
        "/api/personas",
        json={
            "name": "Legacy Meta Persona",
            "description": "legacy",
            "system_prompt": "legacy",
            "focus_areas": ["risk"],
            "tone": "direct",
            "is_active": True,
            "group_id": None,
        },
        headers=headers,
    )
    assert persona_resp.status_code == 201
    persona_id = persona_resp.json()["id"]

    doc_resp = client.post("/api/documents", json={"title": "Legacy Doc"}, headers=headers)
    assert doc_resp.status_code == 201
    doc_id = doc_resp.json()["id"]

    version_resp = client.post(
        f"/api/documents/{doc_id}/versions",
        json={"version_label": "v1", "content": "legacy content"},
        headers=headers,
    )
    assert version_resp.status_code == 201
    version_id = version_resp.json()["id"]

    create_resp = client.post(
        "/api/comments",
        json={
            "persona_id": persona_id,
            "document_version_id": version_id,
            "text": "Needs better structure.",
            "start_offset": 0,
            "end_offset": 5,
            "excerpt": "legacy",
            "output_metadata": {
                "violations": ["missing_quote", "truncated"],
                "legacy_field": "kept",
                "truncated": 1,
            },
        },
        headers=headers,
    )
    assert create_resp.status_code == 201

    created_meta = create_resp.json()["output_metadata"]
    assert set(REQUIRED_OUTPUT_METADATA_KEYS).issubset(created_meta.keys())
    assert VIOLATION_MISSING_QUOTE_EXCERPT in created_meta["violations"]
    assert VIOLATION_TRUNCATED_OUTPUT in created_meta["violations"]
    assert created_meta["legacy_field"] == "kept"

    listed = client.get(f"/api/comments?document_version_id={version_id}", headers=headers)
    assert listed.status_code == 200
    listed_meta = listed.json()[0]["output_metadata"]
    assert set(REQUIRED_OUTPUT_METADATA_KEYS).issubset(listed_meta.keys())
    assert listed_meta["legacy_field"] == "kept"


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
