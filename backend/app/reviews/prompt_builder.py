from __future__ import annotations

import copy
from typing import Any

from app.db import models

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
