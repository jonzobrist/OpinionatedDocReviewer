from app.db import models
from app.reviews.prompt_builder import (
    REQUIRED_PERSONA_EXECUTION_SPEC_FIELDS,
    build_persona_execution_spec,
)
from app.reviews.worker import build_prompt


def test_build_prompt_handles_none_focus_items() -> None:
    prompt = build_prompt(
        name="Risk Reviewer",
        description=None,
        system_prompt=None,
        focus_areas=[None, "security", "", "  compliance  "],
        tone=None,
        content="Sample content",
    )
    assert "Focus areas: security, compliance" in prompt


def test_build_persona_execution_spec_includes_all_required_contract_fields() -> None:
    persona = models.Persona(
        tenant_id="tenant-prompt-spec",
        name="Contract Persona",
        description="checks contract fields",
        system_prompt="Review contract consistency.",
        focus_areas=["clarity", "risk"],
        tone="direct",
        reference_notes="Always include evidence.",
        output_requirements={"format": "bullet_list", "max_bullets": 3},
        examples=["- \"quote\" :: clarify wording"],
        sort_order=42,
        is_active=True,
        is_default=False,
        is_system_locked=False,
    )

    spec = build_persona_execution_spec(persona)

    assert set(REQUIRED_PERSONA_EXECUTION_SPEC_FIELDS).issubset(spec.keys())
    assert spec["name"] == persona.name
    assert spec["reference_notes"] == persona.reference_notes
    assert spec["output_requirements"] == persona.output_requirements
    assert spec["examples"] == persona.examples
    assert spec["sort_order"] == 42


def test_build_persona_execution_spec_returns_copies_for_mutable_fields() -> None:
    persona = models.Persona(
        tenant_id="tenant-prompt-spec-copy",
        name="Copy Persona",
        description="copy check",
        system_prompt="Review contract consistency.",
        focus_areas=["clarity"],
        tone="direct",
        reference_notes="notes",
        output_requirements={"format": "bullet_list", "limits": {"max_bullets": 3}},
        examples=["example"],
        sort_order=7,
        is_active=True,
        is_default=False,
        is_system_locked=False,
    )

    spec = build_persona_execution_spec(persona)
    spec["focus_areas"].append("mutated")
    spec["output_requirements"]["max_bullets"] = 99
    spec["output_requirements"]["limits"]["max_bullets"] = 99
    spec["examples"].append("mutated")

    assert persona.focus_areas == ["clarity"]
    assert persona.output_requirements == {
        "format": "bullet_list",
        "limits": {"max_bullets": 3},
    }
    assert persona.examples == ["example"]


def test_build_persona_execution_spec_filters_blank_focus_areas_and_examples() -> None:
    persona = models.Persona(
        tenant_id="tenant-prompt-spec-normalize",
        name="Normalize Persona",
        description="normalize check",
        system_prompt="Review contract consistency.",
        focus_areas=[None, " clarity ", "", "   ", 123],
        tone="direct",
        reference_notes="notes",
        output_requirements={"format": "bullet_list"},
        examples=[None, " example ", "", "   ", 7],
        sort_order=9,
        is_active=True,
        is_default=False,
        is_system_locked=False,
    )

    spec = build_persona_execution_spec(persona)

    assert spec["focus_areas"] == ["clarity", "123"]
    assert spec["examples"] == ["example", "7"]
