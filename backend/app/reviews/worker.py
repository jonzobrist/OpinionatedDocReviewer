from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.db.init_db import seed_default_personas
from app.db.session import SessionLocal
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout, as_completed
from app.reviews.meta_reviewer import ensure_meta_review_run
from app.reviews.parsing import parse_review_output, persist_comment_payloads, normalize_output_requirements, ParsedComment
from app.reviews.prompt_builder import (
    build_persona_execution_spec,
    build_persona_execution_specs,
    build_review_prompt,
    trim_prompt_content,
)
from app.reviews.git_repo import ensure_repo
from app.reviews.review_storage import write_review_and_commit
from datetime import datetime, timezone
from app.reviews.llm_provider import generate_completion, get_provider_name

REVIEW_TIMEOUT_RETRIES = 3
REVIEW_TIMEOUT_BACKOFF_SECONDS = [1, 2, 4]

logger = logging.getLogger(__name__)


def _list_active_personas_for_execution(
    db: Session,
    tenant_id: str,
) -> list[models.Persona]:
    return (
        db.query(models.Persona)
        .filter(models.Persona.tenant_id == tenant_id, models.Persona.is_active.is_(True))
        .order_by(models.Persona.sort_order.asc(), models.Persona.id.asc())
        .all()
    )


def _auto_trigger_meta_synthesis(
    db: Session,
    tenant_id: str,
    review_job_id: int,
    document_version_id: int,
) -> None:
    if not settings.META_AUTO_SYNTHESIS_ENABLED:
        logger.info(
            "meta_auto_trigger_disabled tenant_id=%s review_job_id=%s document_version_id=%s",
            tenant_id,
            review_job_id,
            document_version_id,
        )
        return

    try:
        ensured = ensure_meta_review_run(
            db=db,
            tenant_id=tenant_id,
            document_version_id=document_version_id,
            review_job_id=review_job_id,
            force=False,
        )
    except ValueError as exc:
        logger.warning(
            "meta_auto_trigger_skipped tenant_id=%s review_job_id=%s document_version_id=%s reason=%s",
            tenant_id,
            review_job_id,
            document_version_id,
            exc,
        )
        return
    except Exception:
        logger.exception(
            "meta_auto_trigger_failed tenant_id=%s review_job_id=%s document_version_id=%s",
            tenant_id,
            review_job_id,
            document_version_id,
        )
        return

    logger.info(
        "meta_auto_triggered tenant_id=%s review_job_id=%s document_version_id=%s meta_run_id=%s resolution=%s status=%s",
        tenant_id,
        review_job_id,
        document_version_id,
        ensured.run.id,
        ensured.resolution,
        ensured.run.status,
    )


def run_review_job(review_job_id: int, tenant_id: str) -> None:
    db = SessionLocal()
    try:
        job = (
            db.query(models.ReviewJob)
            .filter(
                models.ReviewJob.id == review_job_id,
                models.ReviewJob.tenant_id == tenant_id,
            )
            .first()
        )
        if not job:
            return

        job.status = "running"
        db.commit()

        version = (
            db.query(models.DocumentVersion)
            .filter(
                models.DocumentVersion.id == job.document_version_id,
                models.DocumentVersion.tenant_id == tenant_id,
            )
            .first()
        )
        if not version:
            job.status = "failed"
            db.commit()
            return

        personas = _list_active_personas_for_execution(db, tenant_id)
        if not personas:
            seed_default_personas(tenant_id=tenant_id, db=db)
            personas = _list_active_personas_for_execution(db, tenant_id)

        persona_specs = build_persona_execution_specs(personas)

        results: list[dict] = []
        max_workers = max(1, min(len(persona_specs), 6))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {}
            for spec in persona_specs:
                print(f"[review] Persona {spec['id']} starting", flush=True)
                future = executor.submit(generate_comments_for_spec, spec, version.content)
                future_map[future] = spec

            for future in as_completed(future_map):
                spec = future_map[future]
                try:
                    comments = _normalize_parsed_comments(future.result(), spec.get("output_requirements"))
                    comment_texts = [entry.text for entry in comments]
                    persist_comments(
                        db,
                        tenant_id,
                        version.id,
                        spec["id"],
                        review_job_id,
                        comments,
                        version.content,
                    )
                    results.append(
                        {
                            "persona_id": spec["id"],
                            "persona_name": spec["name"],
                            "comments": comment_texts,
                            "output_metadata": [entry.output_metadata for entry in comments],
                        }
                    )
                    print(
                        f"[review] Persona {spec['id']} completed ({len(comment_texts)} comments)",
                        flush=True,
                    )
                except Exception as exc:
                    print(f"[review] Persona {spec['id']} failed: {exc}", flush=True)
                    failure = ParsedComment(
                        text=f"Review failed: {exc}",
                        output_metadata={
                            "requirements": normalize_output_requirements(spec.get("output_requirements")),
                            "violations": ["review_failed"],
                            "used_fallback": True,
                            "truncated": False,
                        },
                    )
                    persist_comments(
                        db,
                        tenant_id,
                        version.id,
                        spec["id"],
                        review_job_id,
                        [failure],
                        version.content,
                    )
                    results.append(
                        {
                            "persona_id": spec["id"],
                            "persona_name": spec["name"],
                            "comments": [f"Review failed: {exc}"],
                            "output_metadata": [failure.output_metadata],
                            "error": str(exc),
                        }
                    )

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        _auto_trigger_meta_synthesis(
            db=db,
            tenant_id=tenant_id,
            review_job_id=review_job_id,
            document_version_id=version.id,
        )

        if settings.DOC_REPO_ENABLED:
            try:
                repo = ensure_repo(tenant_id, version.document_id)
                payload = {
                    "review_job_id": review_job_id,
                    "document_version_id": version.id,
                    "document_id": version.document_id,
                    "status": job.status,
                    "trigger": job.trigger,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "provider": job.provider,
                    "model": job.model,
                    "results": results,
                }
                write_review_and_commit(repo, version.id, review_job_id, payload)
            except Exception as exc:
                print(f"[review] Failed to write review artifact: {exc}", flush=True)
    except Exception:
        try:
            job = (
                db.query(models.ReviewJob)
                .filter(
                    models.ReviewJob.id == review_job_id,
                    models.ReviewJob.tenant_id == tenant_id,
                )
                .first()
            )
            if job:
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            raise
    finally:
        db.close()


def generate_comments(persona: models.Persona, content: str) -> list[ParsedComment]:
    return generate_comments_for_spec(build_persona_execution_spec(persona), content)


def generate_comments_for_spec(persona: dict, content: str) -> list[ParsedComment]:
    prompt = build_prompt(
        persona["name"],
        persona.get("description"),
        persona.get("system_prompt"),
        persona.get("focus_areas"),
        persona.get("tone"),
        trim_content(content),
        persona.get("reference_notes"),
        persona.get("output_requirements"),
        persona.get("examples"),
    )
    start = time.time()
    print(
        f"[review] Persona {persona['id']} timeout {settings.OPENAI_TIMEOUT_SECONDS}s",
        flush=True,
    )

    text = _generate_with_timeout_retry(prompt)
    print(
        f"[review] {get_provider_name()} call took {time.time() - start:.2f}s",
        flush=True,
    )
    return parse_review_output(text, persona.get("output_requirements"))


def _generate_with_timeout_retry(prompt: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, REVIEW_TIMEOUT_RETRIES + 1):
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(generate_completion, prompt)
        try:
            return future.result(timeout=settings.OPENAI_TIMEOUT_SECONDS)
        except FutureTimeout as exc:
            future.cancel()
            last_error = TimeoutError(f"{get_provider_name()} request timed out")
            if attempt < REVIEW_TIMEOUT_RETRIES:
                time.sleep(REVIEW_TIMEOUT_BACKOFF_SECONDS[min(attempt - 1, len(REVIEW_TIMEOUT_BACKOFF_SECONDS) - 1)])
        except Exception as exc:
            message = str(exc).lower()
            last_error = exc
            if "timeout" in message and attempt < REVIEW_TIMEOUT_RETRIES:
                time.sleep(REVIEW_TIMEOUT_BACKOFF_SECONDS[min(attempt - 1, len(REVIEW_TIMEOUT_BACKOFF_SECONDS) - 1)])
            else:
                raise
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
    raise TimeoutError(f"{get_provider_name()} request timed out after {REVIEW_TIMEOUT_RETRIES} attempts") from last_error


def build_prompt(
    name: str,
    description: str | None,
    system_prompt: str | None,
    focus_areas: list[str] | None,
    tone: str | None,
    content: str,
    reference_notes: str | None = None,
    output_requirements: dict | None = None,
    examples: list[str] | None = None,
) -> str:
    return build_review_prompt(
        name=name,
        description=description,
        system_prompt=system_prompt,
        focus_areas=focus_areas,
        tone=tone,
        content=content,
        reference_notes=reference_notes,
        output_requirements=output_requirements,
        examples=examples,
    )


def trim_content(content: str) -> str:
    return trim_prompt_content(content, settings.OPENAI_MAX_INPUT_CHARS)


def _normalize_output_metadata(
    output_metadata: dict | None,
    requirements: dict,
    *,
    default_violations: list[str] | None = None,
    default_used_fallback: bool = False,
) -> dict:
    normalized = dict(output_metadata) if isinstance(output_metadata, dict) else {}

    requirement_source = normalized.get("requirements")
    normalized["requirements"] = normalize_output_requirements(
        requirement_source if isinstance(requirement_source, dict) else requirements
    )

    violations_value = normalized.get("violations")
    if isinstance(violations_value, list):
        normalized["violations"] = [
            str(item).strip()
            for item in violations_value
            if item is not None and str(item).strip()
        ]
    elif default_violations is not None:
        normalized["violations"] = default_violations
    else:
        normalized["violations"] = []

    normalized["used_fallback"] = bool(normalized.get("used_fallback", default_used_fallback))
    normalized["truncated"] = bool(normalized.get("truncated", False))
    return normalized


def _normalize_parsed_comments(raw_comments: list[ParsedComment] | list[str], output_requirements: dict | None) -> list[ParsedComment]:
    if not raw_comments:
        return []
    normalized: list[ParsedComment] = []
    requirements = normalize_output_requirements(output_requirements)
    for entry in raw_comments:
        if isinstance(entry, ParsedComment):
            normalized.append(
                ParsedComment(
                    text=entry.text,
                    output_metadata=_normalize_output_metadata(
                        entry.output_metadata,
                        requirements,
                    ),
                )
            )
            continue
        normalized.append(
            ParsedComment(
                text=str(entry),
                output_metadata=_normalize_output_metadata(
                    None,
                    requirements,
                    default_violations=["unstructured_output"],
                    default_used_fallback=True,
                ),
            )
        )
    return normalized


def persist_comments(
    db: Session,
    tenant_id: str,
    version_id: int,
    persona_id: int,
    review_job_id: int,
    comments: list[ParsedComment],
    content: str,
) -> None:
    for comment, excerpt, start, end, output_metadata in persist_comment_payloads(comments, content):
        db.add(
            models.Comment(
                tenant_id=tenant_id,
                document_version_id=version_id,
                review_job_id=review_job_id,
                persona_id=persona_id,
                text=comment,
                start_offset=start,
                end_offset=end,
                excerpt=excerpt,
                output_metadata=output_metadata or {},
            )
        )
    db.commit()


def retry_failed_persona_in_job(
    review_job_id: int,
    tenant_id: str,
    persona_id: int,
) -> int:
    db = SessionLocal()
    try:
        job = (
            db.query(models.ReviewJob)
            .filter(
                models.ReviewJob.id == review_job_id,
                models.ReviewJob.tenant_id == tenant_id,
            )
            .first()
        )
        if not job:
            return 0
        version = (
            db.query(models.DocumentVersion)
            .filter(
                models.DocumentVersion.id == job.document_version_id,
                models.DocumentVersion.tenant_id == tenant_id,
            )
            .first()
        )
        if not version:
            return 0
        persona = (
            db.query(models.Persona)
            .filter(
                models.Persona.tenant_id == tenant_id,
                models.Persona.id == persona_id,
            )
            .first()
        )
        if not persona:
            return 0

        db.query(models.Comment).filter(
            models.Comment.tenant_id == tenant_id,
            models.Comment.review_job_id == review_job_id,
            models.Comment.persona_id == persona_id,
            models.Comment.text.like("Review failed:%"),
        ).delete(synchronize_session=False)
        db.commit()

        spec = build_persona_execution_spec(persona)
        try:
            comments = _normalize_parsed_comments(
                generate_comments_for_spec(spec, version.content),
                spec.get("output_requirements"),
            )
        except Exception as exc:
            logger.exception(
                "retry_persona_generation_failed review_job_id=%s persona_id=%s tenant_id=%s",
                review_job_id,
                persona_id,
                tenant_id,
            )
            comments = [
                ParsedComment(
                    text=f"Review failed: {exc}",
                    output_metadata={
                        "requirements": normalize_output_requirements(spec.get("output_requirements")),
                        "violations": ["review_failed"],
                        "used_fallback": True,
                        "truncated": False,
                    },
                )
            ]

        persist_comments(
            db,
            tenant_id,
            version.id,
            persona.id,
            review_job_id,
            comments,
            version.content,
        )
        return len(comments)
    finally:
        db.close()
