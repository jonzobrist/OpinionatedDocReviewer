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
