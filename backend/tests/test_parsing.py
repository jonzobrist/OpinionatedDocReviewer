from app.reviews.parsing import normalize_comment_text, persist_comment_payloads, ParsedComment


def test_normalize_comment_text_strips_empty_quote_prefix() -> None:
    assert normalize_comment_text('"" :: tighten this sentence') == "tighten this sentence"
    assert normalize_comment_text('" " :: tighten this sentence') == "tighten this sentence"


def test_persist_comment_payloads_uses_normalized_text() -> None:
    content = "Token expiration behavior must be explicit."
    comments = [ParsedComment(text='"" :: clarify token expiration behavior', output_metadata={})]
    payloads = persist_comment_payloads(comments, content)
    assert len(payloads) == 1
    comment, _excerpt, _start, _end, _meta = payloads[0]
    assert comment == "clarify token expiration behavior"
