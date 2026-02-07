from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.db.init_db import seed_default_personas
from app.db.session import SessionLocal
from app.reviews.openai_client import get_openai_client
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout, as_completed
from app.reviews.parsing import parse_bullets, persist_comment_payloads
from app.reviews.git_repo import ensure_repo
from app.reviews.review_storage import write_review_and_commit
from datetime import datetime, timezone


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

        personas = (
            db.query(models.Persona)
            .filter(models.Persona.tenant_id == tenant_id, models.Persona.is_active.is_(True))
            .order_by(models.Persona.id.asc())
            .all()
        )
        if not personas:
            seed_default_personas(tenant_id=tenant_id, db=db)
            personas = (
                db.query(models.Persona)
                .filter(models.Persona.tenant_id == tenant_id, models.Persona.is_active.is_(True))
                .order_by(models.Persona.id.asc())
                .all()
            )

        persona_specs = [
            {
                "id": persona.id,
                "name": persona.name,
                "description": persona.description,
                "system_prompt": persona.system_prompt,
                "focus_areas": persona.focus_areas,
                "tone": persona.tone,
            }
            for persona in personas
        ]

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
                    comments = future.result()
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
                            "comments": comments,
                        }
                    )
                    print(
                        f"[review] Persona {spec['id']} completed ({len(comments)} comments)",
                        flush=True,
                    )
                except Exception as exc:
                    print(f"[review] Persona {spec['id']} failed: {exc}", flush=True)
                    persist_comments(
                        db,
                        tenant_id,
                        version.id,
                        spec["id"],
                        review_job_id,
                        [f"Review failed: {exc}"],
                        version.content,
                    )
                    results.append(
                        {
                            "persona_id": spec["id"],
                            "persona_name": spec["name"],
                            "comments": [f"Review failed: {exc}"],
                            "error": str(exc),
                        }
                    )

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
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
                    "model": settings.OPENAI_MODEL,
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


def generate_comments(persona: models.Persona, content: str) -> list[str]:
    return generate_comments_for_spec(
        {
            "id": persona.id,
            "name": persona.name,
            "description": persona.description,
            "system_prompt": persona.system_prompt,
            "focus_areas": persona.focus_areas,
            "tone": persona.tone,
        },
        content,
    )


def generate_comments_for_spec(persona: dict, content: str) -> list[str]:
    client = get_openai_client()
    prompt = build_prompt(
        persona["name"],
        persona.get("description"),
        persona.get("system_prompt"),
        persona.get("focus_areas"),
        persona.get("tone"),
        trim_content(content),
    )
    start = time.time()
    print(
        f"[review] Persona {persona['id']} timeout {settings.OPENAI_TIMEOUT_SECONDS}s",
        flush=True,
    )

    def _call():
        return client.responses.create(
            model=settings.OPENAI_MODEL,
            input=prompt,
            max_output_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=settings.OPENAI_TEMPERATURE,
        )

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_call)
    try:
        response = future.result(timeout=settings.OPENAI_TIMEOUT_SECONDS)
    except FutureTimeout:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise TimeoutError("OpenAI request timed out")
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    print(f"[review] OpenAI call took {time.time() - start:.2f}s", flush=True)
    text = response.output_text
    return parse_bullets(text)


def build_prompt(
    name: str,
    description: str | None,
    system_prompt: str | None,
    focus_areas: list[str] | None,
    tone: str | None,
    content: str,
) -> str:
    focus = ", ".join(focus_areas or []) if focus_areas else "general quality"
    voice = tone or "direct and constructive"
    summary = description or ""
    return (
        "You are a document review persona.\n"
        f"Name: {name}\n"
        f"Description: {summary}\n"
        f"System prompt: {system_prompt or ''}\n"
        f"Focus areas: {focus}\n"
        f"Tone: {voice}\n\n"
        "Review the document below and provide 3-6 concise bullet comments. "
        "Each bullet should be a single actionable observation. "
        "If referencing text, include a short excerpt in quotes.\n\n"
        "Document:\n"
        f"{content}"
    )


def trim_content(content: str) -> str:
    if settings.OPENAI_MAX_INPUT_CHARS <= 0:
        return content
    return content[: settings.OPENAI_MAX_INPUT_CHARS]


def persist_comments(
    db: Session,
    tenant_id: str,
    version_id: int,
    persona_id: int,
    review_job_id: int,
    comments: list[str],
    content: str,
) -> None:
    for comment, excerpt, start, end in persist_comment_payloads(comments, content):
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
            )
        )
    db.commit()
