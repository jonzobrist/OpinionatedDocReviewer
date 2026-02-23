from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import models
from app.reviews.llm_provider import (
    LLMProviderError,
    generate_completion,
    get_model_label,
    get_provider_name,
)

ALLOWED_CATEGORIES = {"structure", "clarity", "technical", "security", "accessibility", "style"}
ALLOWED_PRIORITIES = {"critical", "high", "medium", "low"}
ALLOWED_IMPACT = {"high", "medium", "low"}
ALLOWED_EFFORT = {"high", "medium", "low"}
ALLOWED_STATUS = {"open", "planned", "in_progress", "blocked", "resolved"}
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
TOKEN_RE = re.compile(r"[a-z0-9]+")

PRIORITY_SCORE = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0}
IMPACT_SCORE = {"high": 3.0, "medium": 2.0, "low": 1.0}
EFFORT_SCORE = {"low": 3.0, "medium": 2.0, "high": 1.0}

logger = logging.getLogger(__name__)


@dataclass
class CommentGroup:
    start_offset: int
    end_offset: int
    comments: list[models.Comment]


@dataclass
class MetaDirectiveCandidate:
    content: str
    category: str
    priority: str
    impact: str
    effort: str
    confidence: float
    why_now: str | None
    recommended_change: str | None
    verification_step: str | None
    status: str
    assignee: str | None
    due_at: str | None
    rank_score: float
    start_offset: int
    end_offset: int
    order_index: int
    contributing_reviewers: list[str]
    source_comments: list[models.Comment]
    is_unsynthesized: bool


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

    focus_areas = ", ".join(settings.meta_agent_focus_areas_list)
    examples = settings.meta_agent_examples_list
    examples_line = ""
    if examples:
        examples_line = f"Examples to emulate:\n{json.dumps(examples, ensure_ascii=False)}\n\n"

    return (
        f"You are {settings.META_AGENT_NAME}. {settings.META_AGENT_DESCRIPTION}\n"
        f"System guidance: {settings.META_AGENT_SYSTEM_PROMPT}\n"
        f"Focus areas: {focus_areas}\n"
        f"Tone: {settings.META_AGENT_TONE}\n"
        f"Reference notes: {settings.META_AGENT_REFERENCE_NOTES or 'none'}\n"
        f"Output format hint: {settings.META_AGENT_OUTPUT_FORMAT}; max directives: {settings.META_AGENT_OUTPUT_MAX_BULLETS}\n"
        "Return ONLY a valid JSON array; no markdown; no prose.\n"
        "Each item must include keys exactly: content, category, priority, impact, effort, confidence, why_now, recommended_change, verification_step, status, assignee, due_at, contributing_reviewers, location.\n"
        "Rules:\n"
        "- 1-2 sentences max, imperative action; no hedging.\n"
        "- Collapse duplicates into one directive.\n"
        "- Preserve minority critical/security issues even if only one reviewer raised them.\n"
        "- If reviewers conflict, state conflict briefly and pick stronger recommendation.\n"
        "- Omit non-actionable/noise comments.\n"
        "- category: structure|clarity|technical|security|accessibility|style\n"
        "- priority: critical|high|medium|low\n"
        "- impact: high|medium|low\n"
        "- effort: high|medium|low\n"
        "- confidence: float 0..1\n"
        "- status: open|planned|in_progress|blocked|resolved\n"
        "- location must be object with start_offset and end_offset integers.\n"
        f"- contributing_reviewers must be selected from provided reviewer_name values only.\n"
        f"- require_quote_excerpt={str(settings.META_AGENT_OUTPUT_REQUIRE_QUOTE_EXCERPT).lower()}\n"
        f"- require_actionable={str(settings.META_AGENT_OUTPUT_REQUIRE_ACTIONABLE).lower()}\n"
        f"- include_severity={str(settings.META_AGENT_OUTPUT_INCLUDE_SEVERITY).lower()}\n\n"
        f"{examples_line}"
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


def _to_score(
    *,
    priority: str,
    impact: str,
    effort: str,
    confidence: float,
    category: str,
) -> float:
    category_bonus = 0.15 if category == "security" else 0.0
    raw = (
        PRIORITY_SCORE.get(priority, PRIORITY_SCORE["medium"]) * 0.45
        + IMPACT_SCORE.get(impact, IMPACT_SCORE["medium"]) * 0.25
        + EFFORT_SCORE.get(effort, EFFORT_SCORE["medium"]) * 0.15
        + max(0.0, min(1.0, confidence)) * 0.15
        + category_bonus
    )
    return round(raw, 4)


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

    impact = str(item.get("impact", "medium")).strip().lower()
    if impact not in ALLOWED_IMPACT:
        impact = "medium"
    effort = str(item.get("effort", "medium")).strip().lower()
    if effort not in ALLOWED_EFFORT:
        effort = "medium"

    try:
        confidence = float(item.get("confidence", 0.5))
    except Exception:
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    why_now_raw = item.get("why_now")
    why_now = str(why_now_raw).strip() if why_now_raw is not None else None
    why_now = why_now or None

    recommended_change_raw = item.get("recommended_change")
    recommended_change = (
        str(recommended_change_raw).strip() if recommended_change_raw is not None else None
    )
    recommended_change = recommended_change or None

    verification_step_raw = item.get("verification_step")
    verification_step = (
        str(verification_step_raw).strip() if verification_step_raw is not None else None
    )
    verification_step = verification_step or None

    status = str(item.get("status", "open")).strip().lower()
    if status not in ALLOWED_STATUS:
        status = "open"

    assignee_raw = item.get("assignee")
    assignee = str(assignee_raw).strip() if assignee_raw is not None else None
    assignee = assignee or None

    due_at_raw = item.get("due_at")
    due_at = str(due_at_raw).strip() if due_at_raw is not None else None
    due_at = due_at or None

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

    rank_score = _to_score(
        priority=priority,
        impact=impact,
        effort=effort,
        confidence=confidence,
        category=category,
    )

    return {
        "content": content,
        "category": category,
        "priority": priority,
        "impact": impact,
        "effort": effort,
        "confidence": confidence,
        "why_now": why_now,
        "recommended_change": recommended_change,
        "verification_step": verification_step,
        "status": status,
        "assignee": assignee,
        "due_at": due_at,
        "rank_score": rank_score,
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
        comment.persona_id: (
            persona_map.get(comment.persona_id).name
            if persona_map.get(comment.persona_id)
            else f"Reviewer {comment.persona_id}"
        )
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
                if len(directives) >= settings.META_MAX_DIRECTIVES_PER_GROUP:
                    break
        if directives:
            return directives, True
    except LLMProviderError:
        pass

    critical = _critical_comment_exists(group)
    if critical:
        fallback = {
            "content": critical.text,
            "category": "security",
            "priority": "critical",
            "impact": "high",
            "effort": "medium",
            "confidence": 0.8,
            "why_now": "Potential high-impact security risk surfaced by reviewer feedback.",
            "recommended_change": critical.text,
            "verification_step": "Re-run review and verify the risk is addressed in document text.",
            "status": "open",
            "assignee": None,
            "due_at": None,
            "rank_score": _to_score(
                priority="critical",
                impact="high",
                effort="medium",
                confidence=0.8,
                category="security",
            ),
            "contributing_reviewers": [reviewer_name_by_id.get(critical.persona_id, "Reviewer")],
            "start_offset": critical.start_offset,
            "end_offset": max(critical.end_offset, critical.start_offset),
        }
        return ([fallback], False)

    joined = " | ".join(comment.text.strip() for comment in group.comments if comment.text.strip())
    if not joined:
        return [], False
    fallback = {
        "content": joined,
        "category": "clarity",
        "priority": "medium",
        "impact": "medium",
        "effort": "medium",
        "confidence": 0.5,
        "why_now": None,
        "recommended_change": joined,
        "verification_step": "Confirm the updated text addresses all cited reviewer concerns.",
        "status": "open",
        "assignee": None,
        "due_at": None,
        "rank_score": _to_score(
            priority="medium",
            impact="medium",
            effort="medium",
            confidence=0.5,
            category="clarity",
        ),
        "contributing_reviewers": sorted(valid_names),
        "start_offset": group.start_offset,
        "end_offset": group.end_offset,
    }
    return ([fallback], False)


def _tokenize(value: str) -> set[str]:
    return {token for token in TOKEN_RE.findall((value or "").lower()) if len(token) > 2}


def _directive_similarity(left: MetaDirectiveCandidate, right: MetaDirectiveCandidate) -> float:
    left_tokens = _tokenize(left.content)
    right_tokens = _tokenize(right.content)
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens & right_tokens
    union = left_tokens | right_tokens
    if not union:
        return 0.0

    text_score = len(overlap) / len(union)
    location_span = max(left.end_offset, right.end_offset) - min(left.start_offset, right.start_offset)
    near = 1.0 if location_span <= GROUP_ADJACENCY_CHARS else 0.0
    same_category = 1.0 if left.category == right.category else 0.0
    return (text_score * 0.7) + (near * 0.2) + (same_category * 0.1)


def _merge_directives(primary: MetaDirectiveCandidate, duplicate: MetaDirectiveCandidate) -> MetaDirectiveCandidate:
    merged_sources = {comment.id: comment for comment in primary.source_comments}
    for comment in duplicate.source_comments:
        merged_sources.setdefault(comment.id, comment)

    merged_reviewers = list(dict.fromkeys(primary.contributing_reviewers + duplicate.contributing_reviewers))
    better = primary if primary.rank_score >= duplicate.rank_score else duplicate

    primary.content = better.content
    primary.category = better.category
    primary.priority = better.priority
    primary.impact = better.impact
    primary.effort = better.effort
    primary.confidence = max(primary.confidence, duplicate.confidence)
    primary.why_now = primary.why_now or duplicate.why_now
    primary.recommended_change = primary.recommended_change or duplicate.recommended_change
    primary.verification_step = primary.verification_step or duplicate.verification_step
    primary.status = better.status
    primary.assignee = primary.assignee or duplicate.assignee
    primary.due_at = primary.due_at or duplicate.due_at
    primary.rank_score = max(primary.rank_score, duplicate.rank_score)
    primary.start_offset = min(primary.start_offset, duplicate.start_offset)
    primary.end_offset = max(primary.end_offset, duplicate.end_offset)
    primary.contributing_reviewers = merged_reviewers
    primary.source_comments = list(merged_sources.values())
    primary.is_unsynthesized = primary.is_unsynthesized and duplicate.is_unsynthesized
    return primary


def dedupe_directives(candidates: list[MetaDirectiveCandidate]) -> list[MetaDirectiveCandidate]:
    if not candidates:
        return []

    deduped: list[MetaDirectiveCandidate] = []
    threshold = settings.META_GLOBAL_DEDUPE_THRESHOLD
    for candidate in sorted(candidates, key=lambda item: (item.order_index, -item.rank_score)):
        duplicate_idx = None
        for idx, existing in enumerate(deduped):
            if _directive_similarity(candidate, existing) >= threshold:
                duplicate_idx = idx
                break
        if duplicate_idx is None:
            deduped.append(candidate)
        else:
            deduped[duplicate_idx] = _merge_directives(deduped[duplicate_idx], candidate)

    deduped.sort(key=lambda item: (-item.rank_score, item.start_offset, item.order_index))
    for index, candidate in enumerate(deduped):
        candidate.order_index = index
    return deduped


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

    synthesized_all = True
    candidates: list[MetaDirectiveCandidate] = []
    order_index = 0

    try:
        for group in groups:
            directives, synthesized = synthesize_group(group, persona_map, content)
            synthesized_all = synthesized_all and synthesized

            reviewer_name_by_comment_id: dict[int, str] = {}
            for source_comment in group.comments:
                persona = persona_map.get(source_comment.persona_id)
                reviewer_name_by_comment_id[source_comment.id] = (
                    persona.name if persona else f"Reviewer {source_comment.persona_id}"
                )

            for directive in directives:
                selected_names = set(directive["contributing_reviewers"])
                selected_sources = [
                    source_comment
                    for source_comment in group.comments
                    if not selected_names
                    or reviewer_name_by_comment_id[source_comment.id] in selected_names
                ]

                candidates.append(
                    MetaDirectiveCandidate(
                        content=directive["content"],
                        category=directive["category"],
                        priority=directive["priority"],
                        impact=directive["impact"],
                        effort=directive["effort"],
                        confidence=directive["confidence"],
                        why_now=directive["why_now"],
                        recommended_change=directive["recommended_change"],
                        verification_step=directive["verification_step"],
                        status=directive["status"],
                        assignee=directive["assignee"],
                        due_at=directive["due_at"],
                        rank_score=directive["rank_score"],
                        start_offset=directive["start_offset"],
                        end_offset=directive["end_offset"],
                        order_index=order_index,
                        contributing_reviewers=directive["contributing_reviewers"],
                        source_comments=selected_sources,
                        is_unsynthesized=not synthesized,
                    )
                )
                order_index += 1

        deduped = dedupe_directives(candidates)

        for candidate in deduped:
            meta_comment = models.MetaComment(
                tenant_id=tenant_id,
                meta_review_run_id=run.id,
                content=candidate.content,
                category=candidate.category,
                priority=candidate.priority,
                impact=candidate.impact,
                effort=candidate.effort,
                confidence=candidate.confidence,
                why_now=candidate.why_now,
                recommended_change=candidate.recommended_change,
                verification_step=candidate.verification_step,
                status=candidate.status,
                assignee=candidate.assignee,
                due_at=candidate.due_at,
                rank_score=candidate.rank_score,
                start_offset=candidate.start_offset,
                end_offset=candidate.end_offset,
                order_index=candidate.order_index,
                is_unsynthesized=candidate.is_unsynthesized,
            )
            db.add(meta_comment)
            db.flush()

            for source_comment in candidate.source_comments:
                persona = persona_map.get(source_comment.persona_id)
                reviewer_name = persona.name if persona else f"Reviewer {source_comment.persona_id}"
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
