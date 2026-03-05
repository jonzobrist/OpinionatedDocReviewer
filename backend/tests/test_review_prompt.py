from pathlib import Path

from app.db import models
from app.reviews.prompt_builder import (
    REQUIRED_PERSONA_EXECUTION_SPEC_FIELDS,
    build_persona_execution_spec,
    build_review_prompt,
    trim_prompt_content,
    truncate_prompt_examples,
    truncate_prompt_section,
)

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "review_prompt"


def _load_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_build_review_prompt_handles_none_focus_items() -> None:
    prompt = build_review_prompt(
        name="Risk Reviewer",
        description=None,
        system_prompt=None,
        focus_areas=[None, "security", "", "  compliance  "],
        tone=None,
        content="Sample content",
    )
    assert "Focus areas: security, compliance" in prompt


def test_build_review_prompt_renders_output_requirements_and_formatting_constraints() -> None:
    prompt = build_review_prompt(
        name="Risk Reviewer",
        description="reviews risk",
        system_prompt="Be explicit.",
        focus_areas=["risk"],
        tone="direct",
        content="Sample content",
        output_requirements={
            "format": "bullet_list",
            "max_bullets": 2,
            "require_quote_excerpt": True,
            "require_actionable": False,
            "include_severity": True,
        },
    )

    assert "Output requirements:" in prompt
    assert "- Format: bullet_list" in prompt
    assert "- Max bullets: 2" in prompt
    assert "- Require quote excerpt: yes" in prompt
    assert "- Require actionable recommendation: no" in prompt
    assert "- Include severity tags: yes" in prompt
    assert "Formatting constraints:" in prompt
    assert "Use Markdown bullets that start with '- '." in prompt
    assert "Example bullet: - [high] \"<exact excerpt>\" :: <actionable comment>" in prompt
    assert "When quote excerpts are required, use exact document text inside double quotes." in prompt
    assert "When actionable recommendations are required, include a concrete next step." not in prompt


def test_trim_prompt_content_is_deterministic() -> None:
    assert trim_prompt_content("abcdef", max_chars=-1) == "abcdef"
    assert trim_prompt_content("abcdef", max_chars=0) == "abcdef"
    assert trim_prompt_content("abcdef", max_chars=3) == "abc"
    assert trim_prompt_content("abc", max_chars=3) == "abc"


def test_truncate_prompt_section_is_deterministic() -> None:
    text, truncated = truncate_prompt_section("abcdef", max_chars=4)
    assert text == "abcd"
    assert truncated is True

    text, truncated = truncate_prompt_section("abc", max_chars=4)
    assert text == "abc"
    assert truncated is False


def test_truncate_prompt_examples_is_deterministic() -> None:
    examples, truncated = truncate_prompt_examples(
        ["ABCDEFGHIJKL", "MNOPQRSTUV", "WXYZ"],
        max_count=2,
        max_total_chars=15,
    )
    assert examples == ["- ABCDEFGHIJKL", "- MNO"]
    assert truncated is True


def test_build_review_prompt_contract_snapshot() -> None:
    prompt = build_review_prompt(
        name="Snapshot Persona",
        description="Checks deterministic prompt assembly.",
        system_prompt="Review for clarity and risk.",
        focus_areas=["clarity", "risk"],
        tone="direct and constructive",
        content="Document body for snapshot.",
        reference_notes="Always cite policy before recommending edits.",
        output_requirements={
            "format": "bullet_list",
            "max_bullets": 3,
            "require_quote_excerpt": True,
            "require_actionable": True,
            "include_severity": True,
        },
        examples=['[high] "token" :: define expiration behavior'],
    )

    assert prompt == _load_fixture("contract_snapshot.txt")


def test_build_review_prompt_truncation_snapshot() -> None:
    prompt = build_review_prompt(
        name="Truncation Persona",
        description="Verifies deterministic truncation.",
        system_prompt="Follow output contract.",
        focus_areas=["risk"],
        tone="careful",
        content=trim_prompt_content("0123456789ABCDE", max_chars=8),
        reference_notes="abcdefghijklmno",
        output_requirements={
            "format": "bullet_list",
            "max_bullets": 2,
            "require_quote_excerpt": False,
            "require_actionable": True,
            "include_severity": False,
        },
        examples=["ABCDEFGHIJKL", "MNOPQRSTUV", "WXYZ"],
        reference_notes_max_chars=10,
        examples_max_count=2,
        examples_max_total_chars=15,
    )

    assert prompt == _load_fixture("truncation_snapshot.txt")


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
