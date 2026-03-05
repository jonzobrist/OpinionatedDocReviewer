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

VIOLATION_MISSING_QUOTE_EXCERPT = "missing_quote_excerpt"
VIOLATION_MISSING_ACTIONABLE = "missing_actionable"
VIOLATION_MISSING_SEVERITY = "missing_severity"
VIOLATION_UNSTRUCTURED_OUTPUT = "unstructured_output"
VIOLATION_TRUNCATED_OUTPUT = "truncated_output"
VIOLATION_REVIEW_FAILED = "review_failed"

CANONICAL_VIOLATION_TAXONOMY = (
    VIOLATION_MISSING_QUOTE_EXCERPT,
    VIOLATION_MISSING_ACTIONABLE,
    VIOLATION_MISSING_SEVERITY,
    VIOLATION_UNSTRUCTURED_OUTPUT,
    VIOLATION_TRUNCATED_OUTPUT,
    VIOLATION_REVIEW_FAILED,
)

REQUIRED_OUTPUT_METADATA_KEYS = (
    "requirements",
    "violations",
    "used_fallback",
    "truncated",
)

LEGACY_VIOLATION_ALIASES = {
    "missing_quote": VIOLATION_MISSING_QUOTE_EXCERPT,
    "missing_quote_text": VIOLATION_MISSING_QUOTE_EXCERPT,
    "missing_action": VIOLATION_MISSING_ACTIONABLE,
    "missing_severity_tag": VIOLATION_MISSING_SEVERITY,
    "severity_missing": VIOLATION_MISSING_SEVERITY,
    "unstructured": VIOLATION_UNSTRUCTURED_OUTPUT,
    "truncated": VIOLATION_TRUNCATED_OUTPUT,
    "failed_review": VIOLATION_REVIEW_FAILED,
    "review_error": VIOLATION_REVIEW_FAILED,
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


def normalize_comment_output_metadata(
    output_metadata: dict | None,
    output_requirements: dict | None = None,
    *,
    default_violations: list[str] | None = None,
    default_used_fallback: bool = False,
    default_truncated: bool = False,
) -> dict:
    normalized = dict(output_metadata) if isinstance(output_metadata, dict) else {}

    requirements_source = normalized.get("requirements")
    normalized["requirements"] = normalize_output_requirements(
        requirements_source if isinstance(requirements_source, dict) else output_requirements
    )

    violations_source = normalized.get("violations")
    if isinstance(violations_source, list):
        violations = _normalize_violation_list(violations_source)
    elif default_violations is not None:
        violations = _normalize_violation_list(default_violations)
    else:
        violations = []

    normalized["used_fallback"] = _coerce_bool(normalized.get("used_fallback"), default_used_fallback)
    normalized["truncated"] = _coerce_bool(normalized.get("truncated"), default_truncated)

    if normalized["truncated"] and VIOLATION_TRUNCATED_OUTPUT not in violations:
        violations.append(VIOLATION_TRUNCATED_OUTPUT)

    normalized["violations"] = violations
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
    fallback_violations: list[str] = []

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
                fallback_violations = [VIOLATION_UNSTRUCTURED_OUTPUT]
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
        violations = list(fallback_violations)
        if requirements["require_quote_excerpt"] and not _has_quote_excerpt(item):
            violations.append(VIOLATION_MISSING_QUOTE_EXCERPT)
        if requirements["require_actionable"] and not _looks_actionable(item):
            violations.append(VIOLATION_MISSING_ACTIONABLE)
        if requirements["include_severity"] and not SEVERITY_PATTERN.search(item):
            violations.append(VIOLATION_MISSING_SEVERITY)

        output_metadata = normalize_comment_output_metadata(
            {
                "requirements": requirements,
                "violations": violations,
                "used_fallback": used_fallback,
                "truncated": truncated,
            },
            requirements,
        )
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
        payloads.append(
            (
                normalized,
                excerpt,
                start,
                end,
                normalize_comment_output_metadata(comment.output_metadata),
            )
        )
    return payloads


def _normalize_violation_list(values: Iterable[object]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if value is None:
            continue
        token = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        if not token:
            continue
        token = LEGACY_VIOLATION_ALIASES.get(token, token)
        if token not in normalized:
            normalized.append(token)
    return normalized


def _coerce_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "t", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "f", "no", "n", "off", ""}:
            return False
    return bool(value)


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
