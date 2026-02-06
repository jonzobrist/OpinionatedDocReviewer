from app.reviews.parsing import extract_excerpt, parse_bullets


def test_parse_bullets_extracts_lines():
    text = "- First point\n- Second point\nTrailing"
    assert parse_bullets(text) == ["First point", "Second point"]


def test_parse_bullets_falls_back_to_text():
    text = "Single paragraph review."
    assert parse_bullets(text) == ["Single paragraph review."]


def test_extract_excerpt_finds_offset():
    content = "Hello world, this is a test."
    comment = "Consider replacing \"world\" with audience."
    excerpt, start, end = extract_excerpt(content, comment)
    assert excerpt == "world"
    assert start == 6
    assert end == 11
