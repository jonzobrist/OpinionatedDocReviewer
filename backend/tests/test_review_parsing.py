from app.reviews.parsing import (
    REQUIRED_OUTPUT_METADATA_KEYS,
    VIOLATION_MISSING_QUOTE_EXCERPT,
    VIOLATION_MISSING_SEVERITY,
    VIOLATION_TRUNCATED_OUTPUT,
    VIOLATION_UNSTRUCTURED_OUTPUT,
    extract_excerpt,
    parse_review_output,
)


def test_parse_review_output_extracts_lines() -> None:
    text = "- First point\n- Second point\nTrailing"
    parsed = parse_review_output(text, {"max_bullets": 4})
    assert [item.text for item in parsed] == ["First point", "Second point"]


def test_parse_review_output_falls_back_to_text() -> None:
    text = "Single paragraph review."
    parsed = parse_review_output(text, {"max_bullets": 4})
    assert [item.text for item in parsed] == ["Single paragraph review."]
    metadata = parsed[0].output_metadata
    assert metadata["used_fallback"] is True
    assert VIOLATION_UNSTRUCTURED_OUTPUT in metadata["violations"]
    assert set(REQUIRED_OUTPUT_METADATA_KEYS).issubset(metadata.keys())


def test_parse_review_output_flags_missing_quote_and_severity() -> None:
    text = "- Needs work"
    parsed = parse_review_output(
        text,
        {
            "max_bullets": 4,
            "require_quote_excerpt": True,
            "require_actionable": False,
            "include_severity": True,
        },
    )
    assert VIOLATION_MISSING_QUOTE_EXCERPT in parsed[0].output_metadata["violations"]
    assert VIOLATION_MISSING_SEVERITY in parsed[0].output_metadata["violations"]


def test_parse_review_output_adds_truncated_output_violation() -> None:
    parsed = parse_review_output(
        "- one\n- two\n- three",
        {
            "max_bullets": 2,
            "require_quote_excerpt": False,
            "require_actionable": False,
            "include_severity": False,
        },
    )
    assert len(parsed) == 2
    for item in parsed:
        metadata = item.output_metadata
        assert metadata["truncated"] is True
        assert VIOLATION_TRUNCATED_OUTPUT in metadata["violations"]
        assert set(REQUIRED_OUTPUT_METADATA_KEYS).issubset(metadata.keys())


def test_extract_excerpt_finds_offset() -> None:
    content = "Hello world, this is a test."
    comment = "Consider replacing \"world\" with audience."
    excerpt, start, end = extract_excerpt(content, comment)
    assert excerpt == "world"
    assert start == 6
    assert end == 11
