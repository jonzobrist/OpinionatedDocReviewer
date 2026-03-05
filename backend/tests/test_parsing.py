from app.reviews.parsing import (
    REQUIRED_OUTPUT_METADATA_KEYS,
    ParsedComment,
    VIOLATION_MISSING_QUOTE_EXCERPT,
    VIOLATION_REVIEW_FAILED,
    VIOLATION_TRUNCATED_OUTPUT,
    normalize_comment_output_metadata,
    normalize_comment_text,
    persist_comment_payloads,
)


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


def test_persist_comment_payloads_normalizes_output_metadata_keys() -> None:
    content = "Token expiration behavior must be explicit."
    comments = [ParsedComment(text="clarify token expiration behavior", output_metadata={"legacy": "value"})]
    payloads = persist_comment_payloads(comments, content)
    assert len(payloads) == 1
    _comment, _excerpt, _start, _end, metadata = payloads[0]
    assert metadata["legacy"] == "value"
    assert set(REQUIRED_OUTPUT_METADATA_KEYS).issubset(metadata.keys())


def test_normalize_comment_output_metadata_maps_legacy_violations() -> None:
    normalized = normalize_comment_output_metadata(
        {
            "violations": ["missing_quote", "review_error", "truncated"],
            "used_fallback": "yes",
            "truncated": 1,
        }
    )

    assert VIOLATION_MISSING_QUOTE_EXCERPT in normalized["violations"]
    assert VIOLATION_REVIEW_FAILED in normalized["violations"]
    assert VIOLATION_TRUNCATED_OUTPUT in normalized["violations"]
    assert normalized["used_fallback"] is True
    assert normalized["truncated"] is True
    assert set(REQUIRED_OUTPUT_METADATA_KEYS).issubset(normalized.keys())
