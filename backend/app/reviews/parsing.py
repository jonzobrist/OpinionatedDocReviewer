from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

DEFAULT_OUTPUT_REQUIREMENTS = {
    "format": "bullet_list",
    "max_bullets": 4,
    "require_quote_excerpt": True,
    "require_actionable": True,
    "include_severity": False,
}

SEVERITY_PATTERN = re.compile(r"^\s*\[(low|medium|high)\]", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedComment:
    text: str
    output_metadata: dict


def normalize_output_requirements(requirements: dict | None) -> dict:
    normalized = dict(DEFAULT_OUTPUT_REQUIREMENTS)
    if not requirements:
        return normalized
    for key in DEFAULT_OUTPUT_REQUIREMENTS:
        if key in requirements and requirements[key] is not None:
            normalized[key] = requirements[key]
    if not isinstance(normalized.get("max_bullets"), int):
        normalized["max_bullets"] = DEFAULT_OUTPUT_REQUIREMENTS["max_bullets"]
    if normalized["max_bullets"] <= 0:
        normalized["max_bullets"] = DEFAULT_OUTPUT_REQUIREMENTS["max_bullets"]
    for flag in ("require_quote_excerpt", "require_actionable", "include_severity"):
        normalized[flag] = bool(normalized.get(flag, DEFAULT_OUTPUT_REQUIREMENTS[flag]))
    if not normalized.get("format"):
        normalized["format"] = DEFAULT_OUTPUT_REQUIREMENTS["format"]
    return normalized


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


def parse_review_output(text: str, output_requirements: dict | None = None) -> list[ParsedComment]:
    requirements = normalize_output_requirements(output_requirements)
    use_bullets = requirements["format"] == "bullet_list"
    used_fallback = False
    raw_items: list[str] = []
    if use_bullets:
        bullet_items: list[str] = []
        for line in text.splitlines():
            cleaned = line.strip()
            if cleaned.startswith("- "):
                bullet_items.append(cleaned[2:].strip())
            elif cleaned.startswith("* "):
                bullet_items.append(cleaned[2:].strip())
        if bullet_items:
            raw_items = bullet_items
        else:
            stripped = text.strip()
            if stripped:
                raw_items = [stripped]
                used_fallback = True
    else:
        stripped = text.strip()
        if stripped:
            raw_items = [stripped]
            used_fallback = True

    max_bullets = requirements["max_bullets"]
    truncated = len(raw_items) > max_bullets
    if truncated:
        raw_items = raw_items[:max_bullets]

    parsed: list[ParsedComment] = []
    for item in raw_items:
        violations: list[str] = []
        if requirements["require_quote_excerpt"] and not _has_quote_excerpt(item):
            violations.append("missing_quote_excerpt")
        if requirements["require_actionable"] and not _looks_actionable(item):
            violations.append("missing_actionable")
        if requirements["include_severity"] and not SEVERITY_PATTERN.search(item):
            violations.append("missing_severity")
        output_metadata = {
            "requirements": requirements,
            "violations": violations,
            "used_fallback": used_fallback,
            "truncated": truncated,
        }
        parsed.append(ParsedComment(text=item, output_metadata=output_metadata))
    return parsed


def normalize_comment_text(comment: str) -> str:
    cleaned = (comment or "").strip()
    if not cleaned:
        return ""
    # Remove common malformed empty-quote prefixes, e.g. "\"\" :: comment"
    cleaned = re.sub(r'^\s*["\']{2}\s*::\s*', "", cleaned)
    cleaned = re.sub(r'^\s*["\']\s*["\']\s*::\s*', "", cleaned)
    return cleaned.strip()


def extract_excerpt(content: str, comment: str) -> tuple[str | None, int, int]:
    for pattern in (r"\"([^\"]{5,200})\"", r"'([^']{5,200})'"):
        match = re.search(pattern, comment)
        if not match:
            continue
        excerpt = match.group(1).strip()
        index = content.find(excerpt)
        if index != -1:
            return excerpt, index, index + len(excerpt)
        lowered = content.lower().find(excerpt.lower())
        if lowered != -1:
            return content[lowered : lowered + len(excerpt)], lowered, lowered + len(excerpt)

    # Fallback: use a short phrase from comment text and search in content.
    cleaned = re.sub(r"[^\w\s]", " ", comment).strip()
    tokens = [tok for tok in cleaned.split() if len(tok) > 3]
    if len(tokens) >= 3:
        phrase = " ".join(tokens[:6])
        lowered = content.lower().find(phrase.lower())
        if lowered != -1:
            excerpt = content[lowered : lowered + len(phrase)]
            return excerpt, lowered, lowered + len(excerpt)

    return None, 0, 0


def persist_comment_payloads(
    comments: Iterable[ParsedComment],
    content: str,
) -> list[tuple[str, str | None, int, int, dict]]:
    payloads: list[tuple[str, str | None, int, int, dict]] = []
    for comment in comments:
        normalized = normalize_comment_text(comment.text)
        if not normalized:
            continue
        excerpt, start, end = extract_excerpt(content, normalized)
        payloads.append((normalized, excerpt, start, end, comment.output_metadata))
    return payloads


def _has_quote_excerpt(comment: str) -> bool:
    return bool(re.search(r"\"[^\"]{3,}\"", comment))


def _looks_actionable(comment: str) -> bool:
    lowered = comment.lower()
    for keyword in (
        "should",
        "consider",
        "recommend",
        "add",
        "remove",
        "clarify",
        "define",
        "explain",
        "avoid",
        "rename",
        "split",
        "expand",
        "tighten",
        "shorten",
        "replace",
        "fix",
        "update",
        "rephrase",
        "use ",
    ):
        if keyword in lowered:
            return True
    return False
