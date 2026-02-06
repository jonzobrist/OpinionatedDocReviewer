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
    match = re.search(r"\"([^\"]{5,200})\"", comment)
    if not match:
        return None, 0, 0
    excerpt = match.group(1)
    index = content.find(excerpt)
    if index == -1:
        return excerpt, 0, 0
    return excerpt, index, index + len(excerpt)


def persist_comment_payloads(
    comments: Iterable[str],
    content: str,
) -> list[tuple[str, str | None, int, int]]:
    payloads: list[tuple[str, str | None, int, int]] = []
    for comment in comments:
        excerpt, start, end = extract_excerpt(content, comment)
        payloads.append((comment, excerpt, start, end))
    return payloads
