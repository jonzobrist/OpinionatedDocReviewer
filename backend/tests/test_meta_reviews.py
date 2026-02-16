import json

from app.reviews.meta_reviewer import group_comments_by_location


def _seed_review_data(client, headers):
    persona_a = client.post(
        "/api/personas",
        json={
            "name": "A",
            "description": "a",
            "system_prompt": "prompt a",
            "focus_areas": [],
            "tone": "direct",
            "is_active": True,
            "group_id": None,
        },
        headers=headers,
    ).json()
    persona_b = client.post(
        "/api/personas",
        json={
            "name": "B",
            "description": "b",
            "system_prompt": "prompt b",
            "focus_areas": [],
            "tone": "direct",
            "is_active": True,
            "group_id": None,
        },
        headers=headers,
    ).json()
    doc = client.post("/api/documents", json={"title": "Doc"}, headers=headers).json()
    version = client.post(
        f"/api/documents/{doc['id']}/versions",
        json={"version_label": "v1", "content": "alpha beta gamma delta epsilon zeta eta theta"},
        headers=headers,
    ).json()
    job = client.post(
        "/api/review-jobs",
        json={"document_version_id": version["id"], "trigger": "manual"},
        headers=headers,
    ).json()
    client.post(
        "/api/comments",
        json={
            "document_version_id": version["id"],
            "review_job_id": job["id"],
            "persona_id": persona_a["id"],
            "text": "Clarify intro sentence.",
            "start_offset": 0,
            "end_offset": 12,
            "excerpt": "alpha beta",
        },
        headers=headers,
    )
    client.post(
        "/api/comments",
        json={
            "document_version_id": version["id"],
            "review_job_id": job["id"],
            "persona_id": persona_b["id"],
            "text": "Security: token handling is vague.",
            "start_offset": 10,
            "end_offset": 28,
            "excerpt": "beta gamma delta",
        },
        headers=headers,
    )
    return version, job


def test_meta_review_create_and_cache(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta"}
    version, job = _seed_review_data(client, headers)

    llm_payload = [
        {
            "content": "Rewrite authentication wording to specify exact token validation and expiration behavior.",
            "category": "security",
            "priority": "high",
            "contributing_reviewers": ["A", "B"],
            "location": {"start_offset": 0, "end_offset": 28},
        }
    ]

    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: json.dumps(llm_payload),
    )

    create_resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": job["id"]},
        headers=headers,
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["status"] == "completed"
    assert body["is_synthesized"] is True
    assert len(body["comments"]) == 1
    assert body["comments"][0]["priority"] == "high"
    assert len(body["comments"][0]["sources"]) >= 1

    create_again = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": job["id"]},
        headers=headers,
    )
    assert create_again.status_code == 201
    assert create_again.json()["id"] == body["id"]

    latest_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}&review_job_id={job['id']}",
        headers=headers,
    )
    assert latest_resp.status_code == 200
    assert latest_resp.json()["id"] == body["id"]


def test_meta_review_fallback_unsynthesized(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-fallback"}
    version, job = _seed_review_data(client, headers)
    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: "not-json-response",
    )
    resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": job["id"], "force": True},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_synthesized"] is False
    assert len(body["comments"]) >= 1
    assert any(comment["is_unsynthesized"] for comment in body["comments"])


def test_grouping_by_location_merges_adjacent() -> None:
    class C:
        def __init__(self, cid, s, e):
            self.id = cid
            self.start_offset = s
            self.end_offset = e

    comments = [C(1, 0, 10), C(2, 12, 20), C(3, 300, 350)]
    groups = group_comments_by_location(comments, adjacency_chars=5)
    assert len(groups) == 2
    assert len(groups[0].comments) == 2
    assert groups[0].start_offset == 0


def test_meta_review_guardrail_too_many_comments(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-guardrail"}
    version, job = _seed_review_data(client, headers)
    monkeypatch.setattr("app.reviews.meta_reviewer.MAX_META_COMMENTS_INPUT", 1)
    resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": job["id"], "force": True},
        headers=headers,
    )
    assert resp.status_code == 422
