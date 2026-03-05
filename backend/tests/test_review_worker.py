import json
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.db import models
from app.db.init_db import seed_default_personas
from app.db.session import SessionLocal
from app.reviews.parsing import ParsedComment, normalize_output_requirements
from app.reviews.prompt_builder import REQUIRED_PERSONA_EXECUTION_SPEC_FIELDS
from app.reviews.worker import (
    _auto_trigger_meta_synthesis,
    _generate_with_timeout_retry,
    retry_failed_persona_in_job,
    run_review_job,
)


def _seed_review_context(db, tenant_id: str) -> tuple[models.DocumentVersion, models.ReviewJob]:
    seed_default_personas(tenant_id=tenant_id, db=db)

    doc = models.Document(tenant_id=tenant_id, title="Test Doc")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    version = models.DocumentVersion(
        tenant_id=tenant_id,
        document_id=doc.id,
        version_label="v1",
        content="Hello world.\nThis is a test document.",
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    job = models.ReviewJob(
        tenant_id=tenant_id,
        document_version_id=version.id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return version, job


def _assert_full_persona_contract(spec: dict) -> None:
    assert set(REQUIRED_PERSONA_EXECUTION_SPEC_FIELDS).issubset(spec.keys())
    assert spec["id"] is not None
    assert isinstance(spec["name"], str)
    assert isinstance(spec["focus_areas"], list)
    assert isinstance(spec["output_requirements"], dict)
    assert isinstance(spec["examples"], list)


def _seed_review_context_without_personas(
    db,
    tenant_id: str,
) -> tuple[models.DocumentVersion, models.ReviewJob]:
    doc = models.Document(tenant_id=tenant_id, title="Ordered Test Doc")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    version = models.DocumentVersion(
        tenant_id=tenant_id,
        document_id=doc.id,
        version_label="v1",
        content="Ordered content for persona execution.",
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    job = models.ReviewJob(
        tenant_id=tenant_id,
        document_version_id=version.id,
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return version, job


def _create_persona(
    db,
    tenant_id: str,
    *,
    name: str,
    sort_order: int,
    is_active: bool = True,
) -> models.Persona:
    persona = models.Persona(
        tenant_id=tenant_id,
        name=name,
        description=f"{name} description",
        system_prompt=f"{name} prompt",
        focus_areas=["clarity"],
        tone="direct",
        reference_notes=f"{name} notes",
        output_requirements={"format": "bullet_list", "max_bullets": 2},
        examples=[f"Example for {name}"],
        sort_order=sort_order,
        is_active=is_active,
    )
    db.add(persona)
    db.commit()
    db.refresh(persona)
    return persona


def test_run_review_job_uses_full_persona_contract_payload(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-persona-contract-run"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", False)

        version, job = _seed_review_context(db, tenant_id)

        captured_specs: list[dict] = []

        def _capture_generate_comments_for_spec(persona, _content):
            captured_specs.append(
                {
                    "id": persona.get("id"),
                    "name": persona.get("name"),
                    "description": persona.get("description"),
                    "system_prompt": persona.get("system_prompt"),
                    "focus_areas": list(persona.get("focus_areas") or []),
                    "tone": persona.get("tone"),
                    "reference_notes": persona.get("reference_notes"),
                    "output_requirements": dict(persona.get("output_requirements") or {}),
                    "examples": list(persona.get("examples") or []),
                    "sort_order": persona.get("sort_order"),
                }
            )
            return ['Review: clarify "world" term.']

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            _capture_generate_comments_for_spec,
        )

        run_review_job(job.id, tenant_id)

        assert captured_specs
        for spec in captured_specs:
            _assert_full_persona_contract(spec)
            assert spec["sort_order"] is not None
    finally:
        db.close()


def test_review_worker_executes_personas_in_sort_order_then_id(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = f"tenant-test-persona-order-{uuid4().hex}"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.as_completed", lambda futures: futures)

        version, job = _seed_review_context_without_personas(db, tenant_id)
        late = _create_persona(db, tenant_id, name="Late", sort_order=30)
        early_a = _create_persona(db, tenant_id, name="Early A", sort_order=10)
        early_b = _create_persona(db, tenant_id, name="Early B", sort_order=10)

        execution_order: list[int] = []

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            lambda _persona, _content: ['Review: ordered check.'],
        )

        def _capture_persist_comments(
            _db,
            _tenant_id,
            _version_id,
            persona_id,
            _review_job_id,
            _comments,
            _content,
        ):
            execution_order.append(persona_id)

        monkeypatch.setattr("app.reviews.worker.persist_comments", _capture_persist_comments)

        run_review_job(job.id, tenant_id)

        assert execution_order == [early_a.id, early_b.id, late.id]
    finally:
        db.close()


def test_retry_failed_persona_uses_full_persona_contract_payload(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-persona-contract-retry"
        version, job = _seed_review_context(db, tenant_id)

        persona = (
            db.query(models.Persona)
            .filter(models.Persona.tenant_id == tenant_id, models.Persona.is_active.is_(True))
            .order_by(models.Persona.id.asc())
            .first()
        )
        assert persona is not None

        captured_specs: list[dict] = []

        def _capture_generate_comments_for_spec(persona_spec, _content):
            captured_specs.append(
                {
                    "id": persona_spec.get("id"),
                    "name": persona_spec.get("name"),
                    "description": persona_spec.get("description"),
                    "system_prompt": persona_spec.get("system_prompt"),
                    "focus_areas": list(persona_spec.get("focus_areas") or []),
                    "tone": persona_spec.get("tone"),
                    "reference_notes": persona_spec.get("reference_notes"),
                    "output_requirements": dict(persona_spec.get("output_requirements") or {}),
                    "examples": list(persona_spec.get("examples") or []),
                    "sort_order": persona_spec.get("sort_order"),
                }
            )
            return [
                ParsedComment(
                    text='Clarify "world" term.',
                    output_metadata={},
                )
            ]

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            _capture_generate_comments_for_spec,
        )

        added = retry_failed_persona_in_job(job.id, tenant_id, persona.id)
        assert added == 1
        assert len(captured_specs) == 1

        spec = captured_specs[0]
        _assert_full_persona_contract(spec)
        assert spec["id"] == persona.id
        assert spec["name"] == persona.name
        assert spec["sort_order"] == persona.sort_order
        assert spec["reference_notes"] == persona.reference_notes
        assert spec["output_requirements"] == (persona.output_requirements or {})
        assert spec["examples"] == (persona.examples or [])

        created_comments = (
            db.query(models.Comment)
            .filter(
                models.Comment.tenant_id == tenant_id,
                models.Comment.review_job_id == job.id,
                models.Comment.persona_id == persona.id,
            )
            .all()
        )
        assert len(created_comments) >= 1
        assert any('Clarify "world" term.' in comment.text for comment in created_comments)
    finally:
        db.close()


def test_retry_failed_persona_normalizes_output_metadata_schema(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-persona-retry-metadata"
        _version, job = _seed_review_context(db, tenant_id)

        persona = (
            db.query(models.Persona)
            .filter(models.Persona.tenant_id == tenant_id, models.Persona.is_active.is_(True))
            .order_by(models.Persona.id.asc())
            .first()
        )
        assert persona is not None

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            lambda _persona_spec, _content: [
                ParsedComment(
                    text='Clarify "world" term.',
                    output_metadata={},
                )
            ],
        )

        added = retry_failed_persona_in_job(job.id, tenant_id, persona.id)
        assert added == 1

        created = (
            db.query(models.Comment)
            .filter(
                models.Comment.tenant_id == tenant_id,
                models.Comment.review_job_id == job.id,
                models.Comment.persona_id == persona.id,
            )
            .order_by(models.Comment.id.desc())
            .first()
        )
        assert created is not None
        metadata = created.output_metadata
        assert metadata["requirements"] == normalize_output_requirements(persona.output_requirements)
        assert metadata["violations"] == []
        assert metadata["used_fallback"] is False
        assert metadata["truncated"] is False
    finally:
        db.close()


def test_retry_failed_persona_persists_failure_fallback_metadata(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-persona-retry-fallback"
        _version, job = _seed_review_context(db, tenant_id)

        persona = (
            db.query(models.Persona)
            .filter(models.Persona.tenant_id == tenant_id, models.Persona.is_active.is_(True))
            .order_by(models.Persona.id.asc())
            .first()
        )
        assert persona is not None

        def _raise_generation_error(_persona_spec, _content):
            raise RuntimeError("provider unavailable")

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            _raise_generation_error,
        )

        added = retry_failed_persona_in_job(job.id, tenant_id, persona.id)
        assert added == 1

        failure_comment = (
            db.query(models.Comment)
            .filter(
                models.Comment.tenant_id == tenant_id,
                models.Comment.review_job_id == job.id,
                models.Comment.persona_id == persona.id,
                models.Comment.text.like("Review failed:%"),
            )
            .order_by(models.Comment.id.desc())
            .first()
        )
        assert failure_comment is not None
        metadata = failure_comment.output_metadata
        assert metadata["requirements"] == normalize_output_requirements(persona.output_requirements)
        assert metadata["violations"] == ["review_failed"]
        assert metadata["used_fallback"] is True
        assert metadata["truncated"] is False
    finally:
        db.close()


def test_review_worker_persona_order_is_stable_across_reruns(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = f"tenant-test-persona-order-stable-{uuid4().hex}"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.as_completed", lambda futures: futures)

        version, first_job = _seed_review_context_without_personas(db, tenant_id)
        late = _create_persona(db, tenant_id, name="Late", sort_order=30)
        early_a = _create_persona(db, tenant_id, name="Early A", sort_order=10)
        early_b = _create_persona(db, tenant_id, name="Early B", sort_order=10)
        expected = [early_a.id, early_b.id, late.id]

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            lambda _persona, _content: ['Review: ordered check.'],
        )

        capture = {"current": []}

        def _capture_persist_comments(
            _db,
            _tenant_id,
            _version_id,
            persona_id,
            _review_job_id,
            _comments,
            _content,
        ):
            capture["current"].append(persona_id)

        monkeypatch.setattr("app.reviews.worker.persist_comments", _capture_persist_comments)

        first_order: list[int] = []
        capture["current"] = first_order
        run_review_job(first_job.id, tenant_id)

        second_job = models.ReviewJob(
            tenant_id=tenant_id,
            document_version_id=version.id,
            status="queued",
        )
        db.add(second_job)
        db.commit()
        db.refresh(second_job)

        second_order: list[int] = []
        capture["current"] = second_order
        run_review_job(second_job.id, tenant_id)

        assert first_order == expected
        assert second_order == expected
    finally:
        db.close()


def test_review_worker_generates_comments_and_auto_triggers_meta(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-auto-trigger"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", True)

        version, job = _seed_review_context(db, tenant_id)

        def _fake_generate_comments_for_spec(persona, content):
            return ['Review: clarify "world" term.']

        trigger_calls: dict[str, int] = {"count": 0}

        def _fake_ensure_meta_review_run(
            *,
            db,
            tenant_id,
            document_version_id,
            review_job_id,
            force,
        ):
            trigger_calls["count"] += 1
            trigger_calls["document_version_id"] = document_version_id
            trigger_calls["review_job_id"] = review_job_id
            trigger_calls["force"] = int(force)
            return SimpleNamespace(
                run=SimpleNamespace(id=777, status="completed"),
                resolution="created",
            )

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            _fake_generate_comments_for_spec,
        )
        monkeypatch.setattr(
            "app.reviews.worker.ensure_meta_review_run",
            _fake_ensure_meta_review_run,
        )

        run_review_job(job.id, tenant_id)

        comments = (
            db.query(models.Comment)
            .filter(models.Comment.document_version_id == version.id)
            .all()
        )
        assert len(comments) > 0
        assert comments[0].excerpt in ("world", None)
        assert comments[0].review_job_id == job.id

        db.refresh(job)
        assert job.status == "completed"
        assert trigger_calls["count"] == 1
        assert trigger_calls["document_version_id"] == version.id
        assert trigger_calls["review_job_id"] == job.id
        assert trigger_calls["force"] == 0
    finally:
        db.close()


def test_review_worker_keeps_completed_status_when_meta_auto_trigger_fails(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-auto-trigger-failure"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", True)
        version, job = _seed_review_context(db, tenant_id)

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            lambda _persona, _content: ['Review: clarify "world" term.'],
        )

        def _raise_meta_error(**_kwargs):
            raise RuntimeError("meta synthesis downstream unavailable")

        monkeypatch.setattr("app.reviews.worker.ensure_meta_review_run", _raise_meta_error)

        run_review_job(job.id, tenant_id)

        db.refresh(job)
        assert job.status == "completed"

        comments = (
            db.query(models.Comment)
            .filter(models.Comment.document_version_id == version.id)
            .all()
        )
        assert len(comments) > 0

        runs = (
            db.query(models.MetaReviewRun)
            .filter(
                models.MetaReviewRun.tenant_id == tenant_id,
                models.MetaReviewRun.document_version_id == version.id,
                models.MetaReviewRun.review_job_id == job.id,
            )
            .all()
        )
        assert runs == []
    finally:
        db.close()


def test_review_worker_skips_meta_auto_trigger_when_disabled(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-auto-disabled"
        monkeypatch.setattr("app.reviews.worker.settings.DOC_REPO_ENABLED", False)
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", False)
        version, job = _seed_review_context(db, tenant_id)

        monkeypatch.setattr(
            "app.reviews.worker.generate_comments_for_spec",
            lambda _persona, _content: ['Review: clarify "world" term.'],
        )

        def _should_not_be_called(**_kwargs):
            raise AssertionError("ensure_meta_review_run should not be called when auto trigger is disabled")

        monkeypatch.setattr("app.reviews.worker.ensure_meta_review_run", _should_not_be_called)

        run_review_job(job.id, tenant_id)

        db.refresh(job)
        assert job.status == "completed"

        runs = (
            db.query(models.MetaReviewRun)
            .filter(
                models.MetaReviewRun.tenant_id == tenant_id,
                models.MetaReviewRun.document_version_id == version.id,
                models.MetaReviewRun.review_job_id == job.id,
            )
            .all()
        )
        assert runs == []
    finally:
        db.close()


def test_meta_auto_trigger_is_idempotent_for_duplicate_completion_events(monkeypatch) -> None:
    db = SessionLocal()
    try:
        tenant_id = "tenant-test-meta-idempotent"
        monkeypatch.setattr("app.reviews.worker.settings.META_AUTO_SYNTHESIS_ENABLED", True)

        seed_default_personas(tenant_id=tenant_id, db=db)
        personas = (
            db.query(models.Persona)
            .filter(models.Persona.tenant_id == tenant_id, models.Persona.is_active.is_(True))
            .order_by(models.Persona.id.asc())
            .all()
        )
        assert len(personas) >= 2

        doc = models.Document(tenant_id=tenant_id, title="Doc")
        db.add(doc)
        db.commit()
        db.refresh(doc)

        version = models.DocumentVersion(
            tenant_id=tenant_id,
            document_id=doc.id,
            version_label="v1",
            content="alpha beta gamma delta epsilon",
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        job = models.ReviewJob(
            tenant_id=tenant_id,
            document_version_id=version.id,
            status="completed",
            completed_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        db.add(
            models.Comment(
                tenant_id=tenant_id,
                document_version_id=version.id,
                review_job_id=job.id,
                persona_id=personas[0].id,
                text="Clarify intro sentence.",
                start_offset=0,
                end_offset=10,
                excerpt="alpha beta",
                output_metadata={},
            )
        )
        db.add(
            models.Comment(
                tenant_id=tenant_id,
                document_version_id=version.id,
                review_job_id=job.id,
                persona_id=personas[1].id,
                text="Security: token handling is vague.",
                start_offset=8,
                end_offset=24,
                excerpt="beta gamma delta",
                output_metadata={},
            )
        )
        db.commit()

        synth_calls = {"count": 0}

        def _fake_generate(_prompt: str) -> str:
            synth_calls["count"] += 1
            return json.dumps(
                [
                    {
                        "content": "Specify token validation and expiration rules.",
                        "category": "security",
                        "priority": "high",
                        "impact": "high",
                        "effort": "medium",
                        "confidence": 0.9,
                        "why_now": "Ambiguity can lead to insecure implementation.",
                        "recommended_change": "Add explicit token checks and expiry behavior.",
                        "verification_step": "Re-run review and confirm no unresolved security directives.",
                        "status": "open",
                        "assignee": None,
                        "due_at": None,
                        "contributing_reviewers": [personas[0].name, personas[1].name],
                        "location": {"start_offset": 0, "end_offset": 24},
                    }
                ]
            )

        monkeypatch.setattr("app.reviews.meta_reviewer.generate_completion", _fake_generate)

        _auto_trigger_meta_synthesis(
            db=db,
            tenant_id=tenant_id,
            review_job_id=job.id,
            document_version_id=version.id,
        )
        _auto_trigger_meta_synthesis(
            db=db,
            tenant_id=tenant_id,
            review_job_id=job.id,
            document_version_id=version.id,
        )

        runs = (
            db.query(models.MetaReviewRun)
            .filter(
                models.MetaReviewRun.tenant_id == tenant_id,
                models.MetaReviewRun.document_version_id == version.id,
                models.MetaReviewRun.review_job_id == job.id,
            )
            .all()
        )
        assert len(runs) == 1
        assert synth_calls["count"] == 1
    finally:
        db.close()


def test_generate_with_timeout_retry_retries_on_timeout(monkeypatch) -> None:
    calls = {"count": 0}

    def _fake_generate(_prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise TimeoutError("request timed out")
        return "- \"a\" :: ok"

    monkeypatch.setattr("app.reviews.worker.generate_completion", _fake_generate)
    monkeypatch.setattr("app.reviews.worker.time.sleep", lambda _seconds: None)
    output = _generate_with_timeout_retry("prompt")
    assert output == '- "a" :: ok'
    assert calls["count"] == 3
