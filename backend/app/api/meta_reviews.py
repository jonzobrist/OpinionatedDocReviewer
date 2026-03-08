from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, get_tenant_id
from app.db import models
from app.reviews.meta_reviewer import (
    ensure_meta_review_run,
    normalize_meta_review_run_state,
    run_meta_review,
)
from app.schemas.meta_review import (
    MetaReviewCreate,
    MetaReviewEnsureRead,
    MetaReviewEnsureRequest,
    MetaReviewRunRead,
)

router = APIRouter(prefix="/meta-reviews", tags=["meta-reviews"])
logger = logging.getLogger(__name__)
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class _ParagraphSpan:
    start: int
    end: int


@dataclass
class _SectionSpan:
    title: str
    start: int
    end: int
    paragraphs: list[_ParagraphSpan]


def _load_run(
    db: Session,
    tenant_id: str,
    run_id: int,
) -> models.MetaReviewRun | None:
    return (
        db.query(models.MetaReviewRun)
        .options(
            selectinload(models.MetaReviewRun.comments).selectinload(models.MetaComment.sources)
        )
        .filter(models.MetaReviewRun.tenant_id == tenant_id, models.MetaReviewRun.id == run_id)
        .first()
    )


def _ensure_document_version_exists(db: Session, tenant_id: str, document_version_id: int) -> None:
    version = (
        db.query(models.DocumentVersion)
        .filter(
            models.DocumentVersion.tenant_id == tenant_id,
            models.DocumentVersion.id == document_version_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found")


def _prepare_run_for_response(run: models.MetaReviewRun) -> models.MetaReviewRun:
    normalize_meta_review_run_state(run)
    run.comments.sort(key=lambda item: (-item.rank_score, item.start_offset, item.order_index, item.id))
    return run


def _get_version_content(db: Session, tenant_id: str, document_version_id: int) -> str:
    version = (
        db.query(models.DocumentVersion)
        .filter(
            models.DocumentVersion.tenant_id == tenant_id,
            models.DocumentVersion.id == document_version_id,
        )
        .first()
    )
    return version.content if version else ""


def _build_sections(content: str) -> list[_SectionSpan]:
    if not content.strip():
        return []

    matches = list(HEADING_RE.finditer(content))
    sections: list[_SectionSpan] = []

    def _paragraphs_for_range(start: int, end: int) -> list[_ParagraphSpan]:
        block = content[start:end]
        paragraphs: list[_ParagraphSpan] = []
        cursor = 0
        for line in block.splitlines(keepends=True):
            line_start = start + cursor
            stripped = line.strip()
            if stripped and not HEADING_RE.match(line):
                if paragraphs and line_start <= paragraphs[-1].end + 1:
                    paragraphs[-1].end = max(paragraphs[-1].end, line_start + len(line.rstrip("\n")))
                else:
                    paragraphs.append(
                        _ParagraphSpan(
                            start=line_start,
                            end=line_start + len(line.rstrip("\n")),
                        )
                    )
            cursor += len(line)
        return paragraphs

    if not matches:
        paragraphs = _paragraphs_for_range(0, len(content))
        if paragraphs:
            for index, paragraph in enumerate(paragraphs, start=1):
                sections.append(
                    _SectionSpan(
                        title=f"Paragraph {index}",
                        start=paragraph.start,
                        end=paragraph.end,
                        paragraphs=[paragraph],
                    )
                )
        return sections

    if matches[0].start() > 0 and content[: matches[0].start()].strip():
        end = matches[0].start()
        sections.append(
            _SectionSpan(
                title="Opening",
                start=0,
                end=end,
                paragraphs=_paragraphs_for_range(0, end),
            )
        )

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        title = match.group(1).strip().strip("#").strip()
        sections.append(
            _SectionSpan(
                title=title or f"Section {index + 1}",
                start=start,
                end=end,
                paragraphs=_paragraphs_for_range(start, end),
            )
        )
    return sections


def _section_for_offsets(sections: list[_SectionSpan], start_offset: int, end_offset: int) -> _SectionSpan | None:
    for section in sections:
        if start_offset < section.end and end_offset >= section.start:
            return section
    return None


def _location_label(sections: list[_SectionSpan], start_offset: int, end_offset: int) -> str:
    section = _section_for_offsets(sections, start_offset, end_offset)
    if section is None:
        return f"Offsets {start_offset}-{end_offset}"
    paragraph_number = None
    for index, paragraph in enumerate(section.paragraphs, start=1):
        if start_offset < paragraph.end and end_offset >= paragraph.start:
            paragraph_number = index
            break
    if paragraph_number is None:
        return section.title
    return f"{section.title}, paragraph {paragraph_number}"


def _verdict_for_comments(comments: list[models.MetaComment]) -> str:
    if not comments:
        return "clean"
    severe_count = sum(1 for comment in comments if comment.priority in {"critical", "high"})
    if any(comment.priority == "critical" for comment in comments):
        return "problems"
    if severe_count >= 2:
        return "problems"
    if any(
        comment.priority == "high" and comment.impact == "high" and comment.confidence >= 0.75
        for comment in comments
    ):
        return "problems"
    return "review_needed"


def _clean_sections_for_comments(sections: list[_SectionSpan], comments: list[models.MetaComment]) -> list[str]:
    clean: list[str] = []
    for section in sections:
        if not section.title.strip():
            continue
        overlaps = any(comment.start_offset < section.end and comment.end_offset >= section.start for comment in comments)
        if not overlaps:
            clean.append(section.title)
    return clean


def _clean_statement(verdict: str, clean_sections: list[str]) -> str:
    if verdict == "clean":
        return "Entire document is clean — no significant issues found."
    if clean_sections:
        if len(clean_sections) == 1:
            return f"{clean_sections[0]} is clean — no issues found."
        if len(clean_sections) == 2:
            return f"{clean_sections[0]} and {clean_sections[1]} are clean — no issues found."
        visible = ", ".join(clean_sections[:3])
        remainder = len(clean_sections) - 3
        suffix = f", and {remainder} more" if remainder > 0 else ""
        return f"{visible}{suffix} are clean — no issues found."
    return "No section is clean enough to skip yet."


def _build_summary_payload(run: models.MetaReviewRun, content: str) -> dict | None:
    if run.status != "completed":
        return None

    comments = list(run.comments)
    sections = _build_sections(content)
    clean_sections = _clean_sections_for_comments(sections, comments)
    verdict = _verdict_for_comments(comments)
    attention_points = []
    for comment in comments[:5]:
        attention_points.append(
            {
                "meta_comment_id": comment.id,
                "location": _location_label(sections, comment.start_offset, comment.end_offset),
                "reason": comment.content,
                "priority": comment.priority,
                "start_offset": comment.start_offset,
                "end_offset": comment.end_offset,
                "source_comment_ids": [source.comment_id for source in comment.sources],
            }
        )

    return {
        "verdict": verdict,
        "attention_points": attention_points,
        "clean_sections": clean_sections,
        "clean_statement": _clean_statement(verdict, clean_sections),
    }


def _build_run_metadata_payload(run: models.MetaReviewRun) -> dict:
    normalize_meta_review_run_state(run)
    return {
        "id": run.id,
        "tenant_id": run.tenant_id,
        "document_version_id": run.document_version_id,
        "review_job_id": run.review_job_id,
        "input_hash": run.input_hash,
        "status": run.status,
        "queued_at": run.queued_at,
        "running_at": run.running_at,
        "completed_at": run.completed_at,
        "failed_at": run.failed_at,
        "is_synthesized": run.is_synthesized,
        "provider": run.provider,
        "model": run.model,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "error_details": run.error_details,
        "created_at": run.created_at,
        "comments": [],
        "summary": None,
    }


@router.post("", response_model=MetaReviewRunRead, status_code=201)
def create_meta_review(
    payload: MetaReviewCreate,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    _ensure_document_version_exists(db, tenant_id, payload.document_version_id)
    try:
        run = run_meta_review(
            db=db,
            tenant_id=tenant_id,
            document_version_id=payload.document_version_id,
            review_job_id=payload.review_job_id,
            force=payload.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "meta_synthesis_failed tenant_id=%s document_version_id=%s review_job_id=%s",
            tenant_id,
            payload.document_version_id,
            payload.review_job_id,
        )
        raise HTTPException(status_code=503, detail="Meta synthesis failed") from exc
    loaded = _load_run(db, tenant_id, run.id)
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to load synthesized run")
    prepared = _prepare_run_for_response(loaded)
    payload = MetaReviewRunRead.model_validate(prepared).model_dump()
    payload["summary"] = _build_summary_payload(
        prepared,
        _get_version_content(db, tenant_id, prepared.document_version_id),
    )
    return payload


@router.post("/ensure", response_model=MetaReviewEnsureRead)
def ensure_meta_review(
    payload: MetaReviewEnsureRequest,
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    _ensure_document_version_exists(db, tenant_id, payload.document_version_id)
    try:
        ensured = ensure_meta_review_run(
            db=db,
            tenant_id=tenant_id,
            document_version_id=payload.document_version_id,
            review_job_id=payload.review_job_id,
            force=payload.force,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "meta_ensure_failed tenant_id=%s document_version_id=%s review_job_id=%s",
            tenant_id,
            payload.document_version_id,
            payload.review_job_id,
        )
        raise HTTPException(status_code=503, detail="Meta synthesis failed") from exc

    loaded = _load_run(db, tenant_id, ensured.run.id)
    if not loaded:
        raise HTTPException(status_code=500, detail="Failed to load synthesized run")

    prepared = _prepare_run_for_response(loaded)
    run_payload = MetaReviewRunRead.model_validate(prepared).model_dump()
    run_payload["summary"] = _build_summary_payload(
        prepared,
        _get_version_content(db, tenant_id, prepared.document_version_id),
    )
    run_payload["resolution"] = ensured.resolution
    return run_payload


@router.get("/latest", response_model=MetaReviewRunRead)
def get_latest_meta_review(
    document_version_id: int = Query(gt=0),
    review_job_id: int | None = Query(default=None, gt=0),
    include_comments: bool = Query(default=True),
    db: Session = Depends(get_db),
    tenant_id: str = Depends(get_tenant_id),
) -> dict:
    query = db.query(models.MetaReviewRun).filter(
        models.MetaReviewRun.tenant_id == tenant_id,
        models.MetaReviewRun.document_version_id == document_version_id,
    )
    if include_comments:
        query = query.options(
            selectinload(models.MetaReviewRun.comments).selectinload(models.MetaComment.sources)
        )
    if review_job_id is not None:
        query = query.filter(models.MetaReviewRun.review_job_id == review_job_id).order_by(
            models.MetaReviewRun.created_at.desc(),
            models.MetaReviewRun.id.desc(),
        )
    else:
        # Stale-run guard: prioritize the newest review context first, then recency.
        # Tie-break order for unscoped latest: review_job_id (desc, NULL last), created_at desc, id desc.
        query = query.order_by(
            func.coalesce(models.MetaReviewRun.review_job_id, -1).desc(),
            models.MetaReviewRun.created_at.desc(),
            models.MetaReviewRun.id.desc(),
        )
    run = query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Meta review run not found")
    if include_comments:
        prepared = _prepare_run_for_response(run)
        payload = MetaReviewRunRead.model_validate(prepared).model_dump()
        payload["summary"] = _build_summary_payload(
            prepared,
            _get_version_content(db, tenant_id, prepared.document_version_id),
        )
        return payload
    return _build_run_metadata_payload(run)
