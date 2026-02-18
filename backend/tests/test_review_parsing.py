from app.reviews.parsing import extract_excerpt, parse_review_output


def test_parse_review_output_extracts_lines():
    text = "- First point\n- Second point\nTrailing"
    parsed = parse_review_output(text, {"max_bullets": 4})
    assert [item.text for item in parsed] == ["First point", "Second point"]


def test_parse_review_output_falls_back_to_text():
    text = "Single paragraph review."
    parsed = parse_review_output(text, {"max_bullets": 4})
    assert [item.text for item in parsed] == ["Single paragraph review."]
    assert parsed[0].output_metadata["used_fallback"] is True


def test_parse_review_output_flags_missing_quote_and_severity():
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
    assert "missing_quote_excerpt" in parsed[0].output_metadata["violations"]
    assert "missing_severity" in parsed[0].output_metadata["violations"]


def test_extract_excerpt_finds_offset():
    content = "Hello world, this is a test."
    comment = "Consider replacing \"world\" with audience."
    excerpt, start, end = extract_excerpt(content, comment)
    assert excerpt == "world"
    assert start == 6
    assert end == 11
