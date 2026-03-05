from __future__ import annotations

import copy
from typing import Any

from app.db import models
from app.reviews.parsing import normalize_output_requirements

REQUIRED_PERSONA_EXECUTION_SPEC_FIELDS = (
    "id",
    "name",
    "description",
    "system_prompt",
    "focus_areas",
    "tone",
    "reference_notes",
    "output_requirements",
    "examples",
    "sort_order",
)

PROMPT_REFERENCE_NOTES_MAX_CHARS = 2000
PROMPT_EXAMPLES_MAX_COUNT = 3
PROMPT_EXAMPLES_MAX_TOTAL_CHARS = 2000


def _normalize_focus_areas(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_examples(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_output_requirements(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    return copy.deepcopy(value)


def build_persona_execution_spec(persona: models.Persona) -> dict[str, Any]:
    return {
        "id": persona.id,
        "name": persona.name,
        "description": persona.description,
        "system_prompt": persona.system_prompt,
        "focus_areas": _normalize_focus_areas(persona.focus_areas),
        "tone": persona.tone,
        "reference_notes": persona.reference_notes,
        "output_requirements": _normalize_output_requirements(persona.output_requirements),
        "examples": _normalize_examples(persona.examples),
        "sort_order": persona.sort_order,
    }


def build_persona_execution_specs(personas: list[models.Persona]) -> list[dict[str, Any]]:
    return [build_persona_execution_spec(persona) for persona in personas]


def trim_prompt_content(content: str, max_chars: int) -> str:
    if max_chars <= 0:
        return content
    return content[:max_chars]


def truncate_prompt_section(
    text: str | None,
    *,
    max_chars: int = PROMPT_REFERENCE_NOTES_MAX_CHARS,
) -> tuple[str, bool]:
    source = "" if text is None else str(text)
    if max_chars <= 0:
        return "", bool(source)
    if len(source) <= max_chars:
        return source, False
    return source[:max_chars].rstrip(), True


def truncate_prompt_examples(
    examples: list[str] | None,
    *,
    max_count: int = PROMPT_EXAMPLES_MAX_COUNT,
    max_total_chars: int = PROMPT_EXAMPLES_MAX_TOTAL_CHARS,
) -> tuple[list[str], bool]:
    normalized_examples = _normalize_examples(examples)
    if max_count <= 0 or max_total_chars <= 0:
        return [], bool(normalized_examples)

    trimmed: list[str] = []
    total = 0
    truncated = len(normalized_examples) > max_count

    for example in normalized_examples[:max_count]:
        remaining = max_total_chars - total
        if remaining <= 0:
            truncated = True
            break

        text = example
        if len(text) > remaining:
            text = text[:remaining].rstrip()
            truncated = True

        if not text:
            truncated = True
            continue

        total += len(text)
        trimmed.append(f"- {text}")

    return trimmed, truncated


def build_review_prompt(
    name: str,
    description: str | None,
    system_prompt: str | None,
    focus_areas: list[str] | None,
    tone: str | None,
    content: str,
    reference_notes: str | None = None,
    output_requirements: dict | None = None,
    examples: list[str] | None = None,
    *,
    reference_notes_max_chars: int = PROMPT_REFERENCE_NOTES_MAX_CHARS,
    examples_max_count: int = PROMPT_EXAMPLES_MAX_COUNT,
    examples_max_total_chars: int = PROMPT_EXAMPLES_MAX_TOTAL_CHARS,
) -> str:
    normalized_focus_areas = _normalize_focus_areas(focus_areas)
    focus = ", ".join(normalized_focus_areas) if normalized_focus_areas else "general quality"

    voice = "direct and constructive"
    if tone is not None:
        candidate = str(tone).strip()
        if candidate:
            voice = candidate

    summary = description or ""
    requirements = normalize_output_requirements(output_requirements)
    include_severity = requirements["include_severity"]

    sections = [
        "You are a document review persona.",
        f"Name: {name}",
        f"Description: {summary}",
        f"System prompt: {system_prompt or ''}",
        f"Focus areas: {focus}",
        f"Tone: {voice}",
        "",
        "Output requirements:",
        f"- Format: {requirements['format']}",
        f"- Max bullets: {requirements['max_bullets']}",
        f"- Require quote excerpt: {'yes' if requirements['require_quote_excerpt'] else 'no'}",
        f"- Require actionable recommendation: {'yes' if requirements['require_actionable'] else 'no'}",
        f"- Include severity tags: {'yes' if include_severity else 'no'}",
        "",
        "Formatting constraints:",
    ]

    if requirements["format"] == "bullet_list":
        example_prefix = (
            "- [high] \"<exact excerpt>\" :: <actionable comment>"
            if include_severity
            else "- \"<exact excerpt>\" :: <actionable comment>"
        )
        sections.extend(
            [
                "Use Markdown bullets that start with '- '.",
                f"Example bullet: {example_prefix}",
            ]
        )
    else:
        sections.append("Provide a single response matching the required format above.")

    if requirements["require_quote_excerpt"]:
        sections.append("When quote excerpts are required, use exact document text inside double quotes.")
    if requirements["require_actionable"]:
        sections.append("When actionable recommendations are required, include a concrete next step.")

    cleaned_notes = ""
    if reference_notes is not None:
        cleaned_notes = str(reference_notes).strip()
    if cleaned_notes:
        truncated_notes, notes_truncated = truncate_prompt_section(
            cleaned_notes,
            max_chars=reference_notes_max_chars,
        )
        sections.append("")
        sections.append("Reference notes (always consider):")
        sections.append(truncated_notes)
        if notes_truncated:
            sections.append(f"(Reference notes were truncated to {reference_notes_max_chars} characters.)")

    trimmed_examples, examples_truncated = truncate_prompt_examples(
        examples,
        max_count=examples_max_count,
        max_total_chars=examples_max_total_chars,
    )
    if trimmed_examples:
        sections.append("")
        sections.append("Examples:")
        sections.extend(trimmed_examples)
        if examples_truncated:
            sections.append("(Examples were truncated to fit size limits.)")

    sections.extend(
        [
            "",
            "Document:",
            content,
        ]
    )
    return "\n".join(sections)
