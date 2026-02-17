from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import models
from app.reviews.llm_provider import (
    LLMProviderError,
    generate_completion,
    get_model_label,
    get_provider_name,
)

ALLOWED_CATEGORIES = {"structure", "clarity", "technical", "security", "accessibility", "style"}
ALLOWED_PRIORITIES = {"critical", "high", "medium", "low"}
CRITICAL_HINTS = (
    "critical",
    "security",
    "vulnerability",
    "insecure",
    "data leak",
    "compliance",
    "dangerous",
)
GROUP_ADJACENCY_CHARS = 120
MAX_META_COMMENTS_INPUT = 2000
MAX_META_GROUPS = 500
logger = logging.getLogger(__name__)


@dataclass
class CommentGroup:
    start_offset: int
    end_offset: int
    comments: list[models.Comment]


def build_input_hash(comments: list[models.Comment]) -> str:
    parts = [
        f"{item.id}|{item.review_job_id}|{item.persona_id}|{item.start_offset}|{item.end_offset}|{item.text}"
        for item in sorted(comments, key=lambda c: c.id)
    ]
    payload = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def group_comments_by_location(
    comments: list[models.Comment], adjacency_chars: int = GROUP_ADJACENCY_CHARS
) -> list[CommentGroup]:
    sorted_comments = sorted(comments, key=lambda c: (c.start_offset, c.end_offset, c.id))
    groups: list[CommentGroup] = []
    for comment in sorted_comments:
        if not groups:
            groups.append(
                CommentGroup(
                    start_offset=comment.start_offset,
                    end_offset=max(comment.end_offset, comment.start_offset),
                    comments=[comment],
                )
            )
            continue
        current = groups[-1]
        if comment.start_offset <= current.end_offset + adjacency_chars:
            current.comments.append(comment)
            current.end_offset = max(current.end_offset, comment.end_offset, comment.start_offset)
            continue
        groups.append(
            CommentGroup(
                start_offset=comment.start_offset,
                end_offset=max(comment.end_offset, comment.start_offset),
                comments=[comment],
            )
        )
    return groups


def strip_code_fences(text: str) -> str:
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[-1]
    if body.endswith("```"):
        body = body[:-3]
    return body.strip()


def parse_synthesis_json(text: str) -> list[dict]:
    raw = strip_code_fences(text)
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    out: list[dict] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        out.append(item)
    return out


def _build_prompt(group: CommentGroup, persona_map: dict[int, models.Persona], document_text: str) -> str:
    group_excerpt = document_text[max(0, group.start_offset - 120) : group.end_offset + 120]
    reviewer_entries = []
    for comment in group.comments:
        persona = persona_map.get(comment.persona_id)
        name = persona.name if persona else f"Reviewer {comment.persona_id}"
        reviewer_entries.append(
            {
                "comment_id": comment.id,
                "reviewer_id": comment.persona_id,
                "reviewer_name": name,
                "start_offset": comment.start_offset,
                "end_offset": comment.end_offset,
                "excerpt": comment.excerpt,
                "text": comment.text,
            }
        )
    return (
        "You are a meta reviewer synthesizing reviewer feedback into actionable directives.\n"
        "Return ONLY valid JSON array; no markdown; no prose.\n"
        "Each item must include keys exactly: content, category, priority, contributing_reviewers, location.\n"
        "Rules:\n"
        "- 1-2 sentences max, imperative action; no hedging.\n"
        "- Collapse duplicates into one directive.\n"
        "- Preserve minority critical/security issues even if only one reviewer raised them.\n"
        "- If reviewers conflict, state conflict briefly and pick stronger recommendation.\n"
        "- Omit non-actionable/noise comments.\n"
        "- category must be one of: structure, clarity, technical, security, accessibility, style\n"
        "- priority must be one of: critical, high, medium, low\n"
        "- location must be object with start_offset and end_offset integers.\n"
        f"- Contributing reviewers must be selected from provided reviewer_name values only.\n\n"
        f"Document range under review: start={group.start_offset}, end={group.end_offset}\n"
        f"Local text context:\n{group_excerpt}\n\n"
        f"Reviewer comments JSON:\n{json.dumps(reviewer_entries, ensure_ascii=False)}"
    )


def _critical_comment_exists(group: CommentGroup) -> models.Comment | None:
    for comment in group.comments:
        text = (comment.text or "").lower()
        if any(hint in text for hint in CRITICAL_HINTS):
            return comment
    return None


def _normalize_directive(
    item: dict,
    group: CommentGroup,
    valid_reviewer_names: set[str],
) -> dict | None:
    content = str(item.get("content", "")).strip()
    if not content:
        return None
    category = str(item.get("category", "clarity")).strip().lower()
    if category not in ALLOWED_CATEGORIES:
        category = "clarity"
    priority = str(item.get("priority", "medium")).strip().lower()
    if priority not in ALLOWED_PRIORITIES:
        priority = "medium"
    names = item.get("contributing_reviewers") or []
    contributing_reviewers = [
        str(name).strip() for name in names if str(name).strip() in valid_reviewer_names
    ]
    if not contributing_reviewers:
        contributing_reviewers = sorted(valid_reviewer_names)
    location = item.get("location") or {}
    try:
        start_offset = int(location.get("start_offset", group.start_offset))
        end_offset = int(location.get("end_offset", group.end_offset))
    except Exception:
        start_offset, end_offset = group.start_offset, group.end_offset
    if start_offset > end_offset:
        start_offset, end_offset = end_offset, start_offset
    return {
        "content": content,
        "category": category,
        "priority": priority,
        "contributing_reviewers": contributing_reviewers,
        "start_offset": start_offset,
        "end_offset": end_offset,
    }


def synthesize_group(
    group: CommentGroup,
    persona_map: dict[int, models.Persona],
    document_text: str,
) -> tuple[list[dict], bool]:
    reviewer_name_by_id = {
        comment.persona_id: (persona_map.get(comment.persona_id).name if persona_map.get(comment.persona_id) else f"Reviewer {comment.persona_id}")
        for comment in group.comments
    }
    valid_names = set(reviewer_name_by_id.values())
    prompt = _build_prompt(group, persona_map, document_text)
    try:
        response_text = generate_completion(prompt)
        payload = parse_synthesis_json(response_text)
        directives = []
        for item in payload:
            normalized = _normalize_directive(item, group, valid_names)
            if normalized:
                directives.append(normalized)
        if directives:
            return directives, True
    except LLMProviderError:
        pass

    critical = _critical_comment_exists(group)
    if critical:
        return (
            [
                {
                    "content": critical.text,
                    "category": "security",
                    "priority": "critical",
                    "contributing_reviewers": [reviewer_name_by_id.get(critical.persona_id, "Reviewer")],
                    "start_offset": critical.start_offset,
                    "end_offset": max(critical.end_offset, critical.start_offset),
                }
            ],
            False,
        )

    joined = " | ".join(comment.text.strip() for comment in group.comments if comment.text.strip())
    if not joined:
        return [], False
    return (
        [
            {
                "content": joined,
                "category": "clarity",
                "priority": "medium",
                "contributing_reviewers": sorted(valid_names),
                "start_offset": group.start_offset,
                "end_offset": group.end_offset,
            }
        ],
        False,
    )


def run_meta_review(
    db: Session,
    tenant_id: str,
    document_version_id: int,
    review_job_id: int | None = None,
    force: bool = False,
) -> models.MetaReviewRun:
    started = time.perf_counter()
    effective_review_job_id = review_job_id
    query = db.query(models.Comment).filter(
        models.Comment.tenant_id == tenant_id,
        models.Comment.document_version_id == document_version_id,
    )
    if effective_review_job_id is not None:
        query = query.filter(models.Comment.review_job_id == effective_review_job_id)
    comments = query.order_by(models.Comment.id.asc()).all()

    # If the selected run has no anchored comments yet, fall back to the full
    # version comment set so Meta view still works for users.
    if not comments and effective_review_job_id is not None:
        effective_review_job_id = None
        comments = (
            db.query(models.Comment)
            .filter(
                models.Comment.tenant_id == tenant_id,
                models.Comment.document_version_id == document_version_id,
            )
            .order_by(models.Comment.id.asc())
            .all()
        )

    if not comments:
        raise ValueError("No reviewer comments available yet for meta synthesis.")

    if len(comments) > MAX_META_COMMENTS_INPUT:
        raise ValueError(
            f"Too many source comments for meta synthesis ({len(comments)} > {MAX_META_COMMENTS_INPUT})"
        )

    input_hash = build_input_hash(comments)
    if not force:
        cached = (
            db.query(models.MetaReviewRun)
            .filter(
                models.MetaReviewRun.tenant_id == tenant_id,
                models.MetaReviewRun.document_version_id == document_version_id,
                models.MetaReviewRun.review_job_id == effective_review_job_id,
                models.MetaReviewRun.input_hash == input_hash,
            )
            .order_by(models.MetaReviewRun.id.desc())
            .first()
        )
        if cached:
            return cached

    run = models.MetaReviewRun(
        tenant_id=tenant_id,
        document_version_id=document_version_id,
        review_job_id=effective_review_job_id,
        input_hash=input_hash,
        status="running",
        is_synthesized=True,
        provider=get_provider_name(),
        model=get_model_label(),
    )
    db.add(run)
    db.flush()

    personas = (
        db.query(models.Persona)
        .filter(models.Persona.tenant_id == tenant_id)
        .order_by(models.Persona.id.asc())
        .all()
    )
    persona_map = {persona.id: persona for persona in personas}

    version = (
        db.query(models.DocumentVersion)
        .filter(
            models.DocumentVersion.tenant_id == tenant_id,
            models.DocumentVersion.id == document_version_id,
        )
        .first()
    )
    content = version.content if version else ""
    groups = group_comments_by_location(comments)
    if len(groups) > MAX_META_GROUPS:
        raise ValueError(f"Too many comment groups for meta synthesis ({len(groups)} > {MAX_META_GROUPS})")
    order_index = 0
    synthesized_all = True
    try:
        for group in groups:
            directives, synthesized = synthesize_group(group, persona_map, content)
            synthesized_all = synthesized_all and synthesized
            group_comment_ids = {comment.id for comment in group.comments}
            for directive in directives:
                meta_comment = models.MetaComment(
                    tenant_id=tenant_id,
                    meta_review_run_id=run.id,
                    content=directive["content"],
                    category=directive["category"],
                    priority=directive["priority"],
                    start_offset=directive["start_offset"],
                    end_offset=directive["end_offset"],
                    order_index=order_index,
                    is_unsynthesized=not synthesized,
                )
                db.add(meta_comment)
                db.flush()
                order_index += 1

                selected_names = set(directive["contributing_reviewers"])
                for source_comment in group.comments:
                    persona = persona_map.get(source_comment.persona_id)
                    reviewer_name = persona.name if persona else f"Reviewer {source_comment.persona_id}"
                    if source_comment.id not in group_comment_ids:
                        continue
                    if selected_names and reviewer_name not in selected_names:
                        continue
                    db.add(
                        models.MetaCommentSource(
                            tenant_id=tenant_id,
                            meta_comment_id=meta_comment.id,
                            comment_id=source_comment.id,
                            reviewer_name=reviewer_name,
                            reviewer_id=source_comment.persona_id,
                            original_comment_text=source_comment.text,
                        )
                    )

        run.status = "completed"
        run.is_synthesized = synthesized_all
        run.error_message = None
        db.commit()
    except Exception as exc:
        run.status = "failed"
        run.is_synthesized = False
        run.error_message = str(exc)
        db.commit()
        logger.exception(
            "meta_review_failed tenant=%s version=%s review_job=%s input_hash=%s error=%s",
            tenant_id,
            document_version_id,
            effective_review_job_id,
            input_hash,
            exc,
        )
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "meta_review_completed tenant=%s version=%s review_job=%s groups=%s source_comments=%s synthesized=%s duration_ms=%s",
            tenant_id,
            document_version_id,
            effective_review_job_id,
            len(groups),
            len(comments),
            synthesized_all,
            duration_ms,
        )

    db.refresh(run)
    return run
