from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.db.init_db import seed_default_personas
from app.db.session import SessionLocal
from app.reviews.openai_client import get_openai_client
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from app.reviews.parsing import parse_bullets, persist_comment_payloads


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

        for persona in personas:
            try:
                print(f"[review] Persona {persona.id} starting", flush=True)
                comments = generate_comments(persona, version.content)
                persist_comments(db, tenant_id, version.id, persona.id, comments, version.content)
                print(f"[review] Persona {persona.id} completed ({len(comments)} comments)", flush=True)
            except Exception as exc:
                print(f"[review] Persona {persona.id} failed: {exc}", flush=True)
                persist_comments(
                    db,
                    tenant_id,
                    version.id,
                    persona.id,
                    [f"Review failed: {exc}"],
                    version.content,
                )

        job.status = "completed"
        db.commit()
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
                db.commit()
        finally:
            raise
    finally:
        db.close()


def generate_comments(persona: models.Persona, content: str) -> list[str]:
    client = get_openai_client()
    prompt = build_prompt(persona, trim_content(content))
    start = time.time()
    print(f"[review] Timeout {settings.OPENAI_TIMEOUT_SECONDS}s", flush=True)

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


def build_prompt(persona: models.Persona, content: str) -> str:
    focus = ", ".join(persona.focus_areas) if persona.focus_areas else "general quality"
    tone = persona.tone or "direct and constructive"
    description = persona.description or ""
    return (
        "You are a document review persona.\n"
        f"Name: {persona.name}\n"
        f"Description: {description}\n"
        f"System prompt: {persona.system_prompt}\n"
        f"Focus areas: {focus}\n"
        f"Tone: {tone}\n\n"
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


def parse_bullets(text: str) -> list[str]:
    bullets: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned.startswith("- "):
            bullets.append(cleaned[2:].strip())
        elif cleaned.startswith("* "):
            bullets.append(cleaned[2:].strip())
    if not bullets:
        stripped = text.strip()
        return [stripped] if stripped else []
    return bullets


def persist_comments(
    db: Session,
    tenant_id: str,
    version_id: int,
    persona_id: int,
    comments: list[str],
    content: str,
) -> None:
    for comment, excerpt, start, end in persist_comment_payloads(comments, content):
        db.add(
            models.Comment(
                tenant_id=tenant_id,
                document_version_id=version_id,
                persona_id=persona_id,
                text=comment,
                start_offset=start,
                end_offset=end,
                excerpt=excerpt,
            )
        )
    db.commit()
