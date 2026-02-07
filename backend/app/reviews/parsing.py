from __future__ import annotations

import re
from typing import Iterable


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
    comments: Iterable[str],
    content: str,
) -> list[tuple[str, str | None, int, int]]:
    payloads: list[tuple[str, str | None, int, int]] = []
    for comment in comments:
        excerpt, start, end = extract_excerpt(content, comment)
        payloads.append((comment, excerpt, start, end))
    return payloads
