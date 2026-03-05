import difflib
import itertools
import json
from difflib import SequenceMatcher
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

REVIEW_PROMPT_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "review_prompt"
GOLDEN_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "persona_golden"
GOLDEN_PROMPT_FIXTURE_DIR = GOLDEN_FIXTURE_DIR / "prompts"

EXPECTED_GOLDEN_PERSONA_NAMES = [
    "Clarity Editor",
    "Risk & Compliance",
    "Executive Summary",
    "Nielsen Contrarian",
]

GOLDEN_PROMPT_SNAPSHOT_FILES = {
    "Clarity Editor": "clarity_editor.txt",
    "Risk & Compliance": "risk_and_compliance.txt",
    "Executive Summary": "executive_summary.txt",
    "Nielsen Contrarian": "nielsen_contrarian.txt",
}

MAX_NEAR_DUPLICATE_PROMPT_RATIO = 0.85


def _load_fixture(base_dir: Path, name: str) -> str:
    return (base_dir / name).read_text(encoding="utf-8")


def _load_golden_persona_bundle() -> dict:
    return json.loads(_load_fixture(GOLDEN_FIXTURE_DIR, "persona_bundle_v1.json"))


def _assert_text_fixture(actual: str, *, fixture_path: Path, context: str) -> None:
    expected = fixture_path.read_text(encoding="utf-8")
    if actual == expected:
        return

    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=f"expected/{fixture_path.name}",
            tofile=f"actual/{fixture_path.name}",
            n=2,
        )
    )
    raise AssertionError(f"{context} snapshot mismatch:\n{diff}")


def _build_prompt_for_fixture_persona(persona: dict, document_content: str) -> str:
    return build_review_prompt(
        name=persona["name"],
        description=persona.get("description"),
        system_prompt=persona.get("system_prompt"),
        focus_areas=persona.get("focus_areas"),
        tone=persona.get("tone"),
        content=document_content,
        reference_notes=persona.get("reference_notes"),
        output_requirements=persona.get("output_requirements"),
        examples=persona.get("examples"),
    )


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

    _assert_text_fixture(
        prompt,
        fixture_path=REVIEW_PROMPT_FIXTURE_DIR / "contract_snapshot.txt",
        context="review prompt contract",
    )


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

    _assert_text_fixture(
        prompt,
        fixture_path=REVIEW_PROMPT_FIXTURE_DIR / "truncation_snapshot.txt",
        context="review prompt truncation",
    )


def test_golden_persona_fixture_contains_representative_personas() -> None:
    bundle = _load_golden_persona_bundle()
    names = [persona["name"] for persona in bundle["personas"]]
    assert names == EXPECTED_GOLDEN_PERSONA_NAMES


def test_golden_persona_prompt_snapshots_are_stable() -> None:
    bundle = _load_golden_persona_bundle()
    content = _load_fixture(GOLDEN_FIXTURE_DIR, "sample_document.txt").strip()

    for persona in bundle["personas"]:
        prompt = _build_prompt_for_fixture_persona(persona, content)
        snapshot_name = GOLDEN_PROMPT_SNAPSHOT_FILES[persona["name"]]
        _assert_text_fixture(
            prompt,
            fixture_path=GOLDEN_PROMPT_FIXTURE_DIR / snapshot_name,
            context=f"golden persona prompt ({persona['name']})",
        )


def test_golden_persona_prompts_are_differentiated() -> None:
    bundle = _load_golden_persona_bundle()
    content = _load_fixture(GOLDEN_FIXTURE_DIR, "sample_document.txt").strip()

    prompts = {
        persona["name"]: _build_prompt_for_fixture_persona(persona, content)
        for persona in bundle["personas"]
    }

    for left_name, right_name in itertools.combinations(prompts.keys(), 2):
        left_prompt = prompts[left_name]
        right_prompt = prompts[right_name]
        similarity = SequenceMatcher(None, left_prompt, right_prompt).ratio()
        if similarity < MAX_NEAR_DUPLICATE_PROMPT_RATIO:
            continue

        diff = "".join(
            difflib.unified_diff(
                left_prompt.splitlines(keepends=True),
                right_prompt.splitlines(keepends=True),
                fromfile=f"prompt/{left_name}",
                tofile=f"prompt/{right_name}",
                n=2,
            )
        )
        raise AssertionError(
            "Golden persona prompts became near-duplicates "
            f"({left_name} vs {right_name}, similarity={similarity:.3f} >= {MAX_NEAR_DUPLICATE_PROMPT_RATIO}).\n"
            f"Diff:\n{diff}"
        )


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
