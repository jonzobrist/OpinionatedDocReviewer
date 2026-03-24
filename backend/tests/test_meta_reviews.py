import json

from app.reviews.meta_reviewer import group_comments_by_location


def _seed_review_data(client, headers, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(
            "app.api.review_jobs.enqueue_review_job",
            lambda _job_id, _tenant_id: None,
        )

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


def _add_comments_for_job(
    client,
    headers,
    *,
    document_version_id: int,
    review_job_id: int,
    persona_id_a: int,
    persona_id_b: int,
) -> None:
    client.post(
        "/api/comments",
        json={
            "document_version_id": document_version_id,
            "review_job_id": review_job_id,
            "persona_id": persona_id_a,
            "text": "Clarify latest intent for this review context.",
            "start_offset": 0,
            "end_offset": 14,
            "excerpt": "alpha beta",
        },
        headers=headers,
    )
    client.post(
        "/api/comments",
        json={
            "document_version_id": document_version_id,
            "review_job_id": review_job_id,
            "persona_id": persona_id_b,
            "text": "Security detail remains vague in latest context.",
            "start_offset": 12,
            "end_offset": 30,
            "excerpt": "beta gamma delta",
        },
        headers=headers,
    )


def test_meta_review_create_and_cache(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta"}
    version, job = _seed_review_data(client, headers, monkeypatch)

    llm_payload = [
        {
            "content": "Rewrite authentication wording to specify exact token validation and expiration behavior.",
            "category": "security",
            "priority": "high",
            "impact": "high",
            "effort": "medium",
            "confidence": 0.82,
            "why_now": "This could cause incorrect token handling in production.",
            "recommended_change": "Specify explicit validation and expiration rules.",
            "verification_step": "Run token auth tests and confirm docs include exact rules.",
            "status": "open",
            "assignee": "auth-owner",
            "due_at": "2026-03-01",
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
    assert body["queued_at"] is not None
    assert body["running_at"] is not None
    assert body["completed_at"] is not None
    assert body["failed_at"] is None
    assert body["is_synthesized"] is True
    assert body["error_code"] is None
    assert body["error_message"] is None
    assert body["error_details"] is None
    assert len(body["comments"]) == 1
    assert body["summary"]["verdict"] == "problems"
    assert body["summary"]["attention_points"][0]["meta_comment_id"] == body["comments"][0]["id"]
    assert body["summary"]["attention_points"][0]["reason"] == body["comments"][0]["content"]
    assert body["summary"]["clean_statement"] == "No section is clean enough to skip yet."
    assert body["comments"][0]["priority"] == "high"
    assert body["comments"][0]["impact"] == "high"
    assert body["comments"][0]["effort"] == "medium"
    assert body["comments"][0]["status"] == "open"
    assert body["comments"][0]["rank_score"] > 0
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


def test_latest_meta_review_supports_lightweight_mode_without_comments(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-latest-lightweight"}
    version, job = _seed_review_data(client, headers, monkeypatch)

    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: json.dumps(
            [
                {
                    "content": "Clarify auth flow and explicit token lifecycle.",
                    "category": "security",
                    "priority": "high",
                    "impact": "high",
                    "effort": "low",
                    "confidence": 0.88,
                    "why_now": "Current wording could cause insecure implementations.",
                    "recommended_change": "Define validation and token expiry behavior.",
                    "verification_step": "Confirm security review comments converge to one directive.",
                    "status": "open",
                    "assignee": None,
                    "due_at": None,
                    "contributing_reviewers": ["A", "B"],
                    "location": {"start_offset": 0, "end_offset": 28},
                }
            ]
        ),
    )

    created_resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": job["id"], "force": True},
        headers=headers,
    )
    assert created_resp.status_code == 201

    full_latest_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}&review_job_id={job['id']}",
        headers=headers,
    )
    assert full_latest_resp.status_code == 200
    full_latest = full_latest_resp.json()
    assert len(full_latest["comments"]) >= 1

    lightweight_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}&review_job_id={job['id']}&include_comments=false",
        headers=headers,
    )
    assert lightweight_resp.status_code == 200
    lightweight = lightweight_resp.json()
    assert lightweight["id"] == full_latest["id"]
    assert lightweight["status"] == full_latest["status"]
    assert lightweight["queued_at"] == full_latest["queued_at"]
    assert lightweight["running_at"] == full_latest["running_at"]
    assert lightweight["completed_at"] == full_latest["completed_at"]
    assert lightweight["failed_at"] == full_latest["failed_at"]
    assert lightweight["comments"] == []
    assert lightweight["summary"] is None


def test_latest_meta_review_prefers_newest_review_context_over_stale_created_later(
    client,
    monkeypatch,
) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-latest-guard"}
    version, older_job = _seed_review_data(client, headers, monkeypatch)

    personas_resp = client.get("/api/personas", headers=headers)
    assert personas_resp.status_code == 200
    personas = {item["name"]: item for item in personas_resp.json()}
    assert "A" in personas and "B" in personas

    newer_job_resp = client.post(
        "/api/review-jobs",
        json={"document_version_id": version["id"], "trigger": "manual"},
        headers=headers,
    )
    assert newer_job_resp.status_code == 201
    newer_job = newer_job_resp.json()

    _add_comments_for_job(
        client,
        headers,
        document_version_id=version["id"],
        review_job_id=newer_job["id"],
        persona_id_a=personas["A"]["id"],
        persona_id_b=personas["B"]["id"],
    )

    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: json.dumps(
            [
                {
                    "content": "Specify exact token validation and expiry requirements.",
                    "category": "security",
                    "priority": "high",
                    "impact": "high",
                    "effort": "medium",
                    "confidence": 0.9,
                    "why_now": "Ambiguity can lead to insecure implementation.",
                    "recommended_change": "Document explicit checks and expiry behavior.",
                    "verification_step": "Re-run review to confirm security clarity.",
                    "status": "open",
                    "assignee": None,
                    "due_at": None,
                    "contributing_reviewers": ["A", "B"],
                    "location": {"start_offset": 0, "end_offset": 30},
                }
            ]
        ),
    )

    newer_run_resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": newer_job["id"], "force": True},
        headers=headers,
    )
    assert newer_run_resp.status_code == 201
    newer_run = newer_run_resp.json()

    stale_run_resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": older_job["id"], "force": True},
        headers=headers,
    )
    assert stale_run_resp.status_code == 201
    stale_run = stale_run_resp.json()
    assert stale_run["review_job_id"] == older_job["id"]
    assert stale_run["id"] != newer_run["id"]

    latest_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}",
        headers=headers,
    )
    assert latest_resp.status_code == 200
    latest = latest_resp.json()
    assert latest["review_job_id"] == newer_job["id"]
    assert latest["id"] == newer_run["id"]

    lightweight_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}&include_comments=false",
        headers=headers,
    )
    assert lightweight_resp.status_code == 200
    lightweight = lightweight_resp.json()
    assert lightweight["review_job_id"] == newer_job["id"]
    assert lightweight["id"] == newer_run["id"]
    assert lightweight["comments"] == []


def test_latest_meta_review_prefers_review_context_over_newer_unscoped_run(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-latest-unscoped"}
    version, older_job = _seed_review_data(client, headers, monkeypatch)

    personas_resp = client.get("/api/personas", headers=headers)
    assert personas_resp.status_code == 200
    personas = {item["name"]: item for item in personas_resp.json()}

    newer_job_resp = client.post(
        "/api/review-jobs",
        json={"document_version_id": version["id"], "trigger": "manual"},
        headers=headers,
    )
    assert newer_job_resp.status_code == 201
    newer_job = newer_job_resp.json()

    _add_comments_for_job(
        client,
        headers,
        document_version_id=version["id"],
        review_job_id=newer_job["id"],
        persona_id_a=personas["A"]["id"],
        persona_id_b=personas["B"]["id"],
    )

    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: json.dumps(
            [
                {
                    "content": "Use explicit token validation checks.",
                    "category": "security",
                    "priority": "high",
                    "impact": "high",
                    "effort": "low",
                    "confidence": 0.92,
                    "why_now": "Latest review context surfaced unresolved ambiguity.",
                    "recommended_change": "Add validation, expiry, and fallback behavior.",
                    "verification_step": "Re-run reviewers and confirm security concerns are closed.",
                    "status": "open",
                    "assignee": None,
                    "due_at": None,
                    "contributing_reviewers": ["A", "B"],
                    "location": {"start_offset": 0, "end_offset": 30},
                }
            ]
        ),
    )

    latest_context_resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": newer_job["id"], "force": True},
        headers=headers,
    )
    assert latest_context_resp.status_code == 201
    latest_context_run = latest_context_resp.json()

    no_comment_job_resp = client.post(
        "/api/review-jobs",
        json={"document_version_id": version["id"], "trigger": "manual"},
        headers=headers,
    )
    assert no_comment_job_resp.status_code == 201
    no_comment_job = no_comment_job_resp.json()

    unscoped_resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": no_comment_job["id"], "force": True},
        headers=headers,
    )
    assert unscoped_resp.status_code == 201
    unscoped_run = unscoped_resp.json()
    assert unscoped_run["review_job_id"] is None
    assert unscoped_run["id"] != latest_context_run["id"]

    latest_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}",
        headers=headers,
    )
    assert latest_resp.status_code == 200
    latest = latest_resp.json()
    assert latest["review_job_id"] == newer_job["id"]
    assert latest["id"] == latest_context_run["id"]



def test_latest_meta_review_for_same_context_uses_created_order_tiebreak(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-latest-tiebreak"}
    version, job = _seed_review_data(client, headers, monkeypatch)

    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: json.dumps(
            [
                {
                    "content": "Clarify authentication and access-control boundaries.",
                    "category": "security",
                    "priority": "high",
                    "impact": "high",
                    "effort": "low",
                    "confidence": 0.85,
                    "why_now": "Reviewers flagged ambiguity in control boundaries.",
                    "recommended_change": "Name each auth check and expected behavior.",
                    "verification_step": "Confirm both reviewers no longer raise ambiguity.",
                    "status": "open",
                    "assignee": None,
                    "due_at": None,
                    "contributing_reviewers": ["A", "B"],
                    "location": {"start_offset": 0, "end_offset": 28},
                }
            ]
        ),
    )

    first_resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": job["id"], "force": True},
        headers=headers,
    )
    assert first_resp.status_code == 201
    first = first_resp.json()

    second_resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": job["id"], "force": True},
        headers=headers,
    )
    assert second_resp.status_code == 201
    second = second_resp.json()
    assert second["id"] != first["id"]

    latest_by_job_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}&review_job_id={job['id']}",
        headers=headers,
    )
    assert latest_by_job_resp.status_code == 200
    latest_by_job = latest_by_job_resp.json()
    assert latest_by_job["id"] == second["id"]

    latest_unscoped_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}",
        headers=headers,
    )
    assert latest_unscoped_resp.status_code == 200
    latest_unscoped = latest_unscoped_resp.json()
    assert latest_unscoped["id"] == second["id"]


def test_meta_review_ensure_endpoint_is_idempotent_with_resolution(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-ensure"}
    version, job = _seed_review_data(client, headers, monkeypatch)

    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: json.dumps(
            [
                {
                    "content": "Clarify auth flow and explicit token lifecycle.",
                    "category": "security",
                    "priority": "high",
                    "impact": "high",
                    "effort": "low",
                    "confidence": 0.88,
                    "why_now": "Current wording could cause insecure implementations.",
                    "recommended_change": "Define validation and token expiry behavior.",
                    "verification_step": "Confirm security review comments converge to one directive.",
                    "status": "open",
                    "assignee": None,
                    "due_at": None,
                    "contributing_reviewers": ["A", "B"],
                    "location": {"start_offset": 0, "end_offset": 28},
                }
            ]
        ),
    )

    first_resp = client.post(
        "/api/meta-reviews/ensure",
        json={"document_version_id": version["id"], "review_job_id": job["id"]},
        headers=headers,
    )
    assert first_resp.status_code == 200
    first = first_resp.json()
    assert first["resolution"] == "created"
    assert first["status"] == "completed"

    second_resp = client.post(
        "/api/meta-reviews/ensure",
        json={"document_version_id": version["id"], "review_job_id": job["id"]},
        headers=headers,
    )
    assert second_resp.status_code == 200
    second = second_resp.json()
    assert second["resolution"] == "reused"
    assert second["id"] == first["id"]

    forced_resp = client.post(
        "/api/meta-reviews/ensure",
        json={"document_version_id": version["id"], "review_job_id": job["id"], "force": True},
        headers=headers,
    )
    assert forced_resp.status_code == 200
    forced = forced_resp.json()
    assert forced["resolution"] == "created"
    assert forced["id"] != first["id"]


def test_meta_review_ensure_creates_new_run_when_source_input_changes(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-ensure-input-change"}
    version, job = _seed_review_data(client, headers, monkeypatch)

    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: json.dumps(
            [
                {
                    "content": "Clarify auth flow and explicit token lifecycle.",
                    "category": "security",
                    "priority": "high",
                    "impact": "high",
                    "effort": "low",
                    "confidence": 0.88,
                    "why_now": "Current wording could cause insecure implementations.",
                    "recommended_change": "Define validation and token expiry behavior.",
                    "verification_step": "Confirm security review comments converge to one directive.",
                    "status": "open",
                    "assignee": None,
                    "due_at": None,
                    "contributing_reviewers": ["A", "B"],
                    "location": {"start_offset": 0, "end_offset": 28},
                }
            ]
        ),
    )

    initial_resp = client.post(
        "/api/meta-reviews/ensure",
        json={"document_version_id": version["id"], "review_job_id": job["id"]},
        headers=headers,
    )
    assert initial_resp.status_code == 200
    initial = initial_resp.json()
    assert initial["resolution"] == "created"

    personas_resp = client.get("/api/personas", headers=headers)
    assert personas_resp.status_code == 200
    personas = {item["name"]: item for item in personas_resp.json()}
    assert "A" in personas

    added_comment_resp = client.post(
        "/api/comments",
        json={
            "document_version_id": version["id"],
            "review_job_id": job["id"],
            "persona_id": personas["A"]["id"],
            "text": "Add explicit rule precedence ordering.",
            "start_offset": 2,
            "end_offset": 16,
            "excerpt": "pha beta gamma",
        },
        headers=headers,
    )
    assert added_comment_resp.status_code == 201

    changed_resp = client.post(
        "/api/meta-reviews/ensure",
        json={"document_version_id": version["id"], "review_job_id": job["id"]},
        headers=headers,
    )
    assert changed_resp.status_code == 200
    changed = changed_resp.json()
    assert changed["resolution"] == "created"
    assert changed["id"] != initial["id"]
    assert changed["input_hash"] != initial["input_hash"]

    repeat_resp = client.post(
        "/api/meta-reviews/ensure",
        json={"document_version_id": version["id"], "review_job_id": job["id"]},
        headers=headers,
    )
    assert repeat_resp.status_code == 200
    repeat = repeat_resp.json()
    assert repeat["resolution"] == "reused"
    assert repeat["id"] == changed["id"]


def test_meta_review_failed_run_exposes_safe_error_details(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-failed"}
    version, job = _seed_review_data(client, headers, monkeypatch)

    def _raise_failure(*_args, **_kwargs):
        raise RuntimeError("provider crash sk-live-secret-token")

    monkeypatch.setattr("app.reviews.meta_reviewer.synthesize_group", _raise_failure)

    ensure_resp = client.post(
        "/api/meta-reviews/ensure",
        json={"document_version_id": version["id"], "review_job_id": job["id"], "force": True},
        headers=headers,
    )
    assert ensure_resp.status_code == 503

    latest_resp = client.get(
        f"/api/meta-reviews/latest?document_version_id={version['id']}&review_job_id={job['id']}",
        headers=headers,
    )
    assert latest_resp.status_code == 200
    latest = latest_resp.json()
    assert latest["status"] == "failed"
    assert latest["queued_at"] is not None
    assert latest["running_at"] is not None
    assert latest["completed_at"] is None
    assert latest["failed_at"] is not None
    assert latest["error_code"] == "meta_synthesis_failed"
    assert latest["error_message"] == "Meta synthesis failed. Please retry."
    assert latest["error_details"]["code"] == "meta_synthesis_failed"
    assert latest["error_details"]["message"] == "Meta synthesis failed. Please retry."
    assert latest["error_details"]["retryable"] is True
    assert "sk-live" not in latest["error_message"]



def test_meta_review_fallback_unsynthesized(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-fallback"}
    version, job = _seed_review_data(client, headers, monkeypatch)
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
    assert body["status"] == "completed"
    assert body["queued_at"] is not None
    assert body["running_at"] is not None
    assert body["completed_at"] is not None
    assert body["failed_at"] is None
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
    version, job = _seed_review_data(client, headers, monkeypatch)
    monkeypatch.setattr("app.reviews.meta_reviewer.MAX_META_COMMENTS_INPUT", 1)
    resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": job["id"], "force": True},
        headers=headers,
    )
    assert resp.status_code == 422


def test_meta_review_falls_back_when_selected_review_job_has_no_comments(client, monkeypatch) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-fallback-job"}
    version, job = _seed_review_data(client, headers, monkeypatch)
    later_job = client.post(
        "/api/review-jobs",
        json={"document_version_id": version["id"], "trigger": "manual"},
        headers=headers,
    ).json()
    monkeypatch.setattr(
        "app.reviews.meta_reviewer.generate_completion",
        lambda _: json.dumps(
            [
                {
                    "content": "Tighten security details for token validation.",
                    "category": "security",
                    "priority": "high",
                    "impact": "high",
                    "effort": "low",
                    "confidence": 0.9,
                    "why_now": "Security ambiguity can lead to implementation gaps.",
                    "recommended_change": "Define required checks and fallback behavior.",
                    "verification_step": "Re-run reviewers to confirm no remaining security directives.",
                    "status": "planned",
                    "assignee": "security-owner",
                    "due_at": None,
                    "contributing_reviewers": ["A"],
                    "location": {"start_offset": 0, "end_offset": 20},
                }
            ]
        ),
    )
    resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "review_job_id": later_job["id"], "force": True},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["review_job_id"] is None
    assert len(body["comments"]) == 1


def test_meta_review_returns_422_when_no_comments_exist(client) -> None:
    headers = {"X-Tenant-Id": "tenant-meta-empty"}
    doc = client.post("/api/documents", json={"title": "Doc"}, headers=headers).json()
    version = client.post(
        f"/api/documents/{doc['id']}/versions",
        json={"version_label": "v1", "content": "alpha beta gamma"},
        headers=headers,
    ).json()
    resp = client.post(
        "/api/meta-reviews",
        json={"document_version_id": version["id"], "force": True},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "No reviewer comments available yet" in resp.json()["detail"]
