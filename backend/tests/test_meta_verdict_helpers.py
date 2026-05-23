"""Focused unit tests for the verdict/clean-section helpers in meta_reviews.

These helpers drive the primary go/no-go signal the reviewer sees in the UI.
The route-integration tests only exercised the `problems` verdict path; this
file pins the boundaries around `clean`, `review_needed`, and the clean-section
narrative so future changes cannot silently change the signal.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.api.meta_reviews import (
    _build_sections,
    _clean_sections_for_comments,
    _clean_statement,
    _location_label,
    _verdict_for_comments,
)


@dataclass
class FakeComment:
    """Minimal stand-in for MetaComment rows.

    The verdict/clean-section helpers only read the fields below. Using a
    dataclass avoids building full SQLAlchemy-mapped instances in these unit
    tests, which keeps them fast and independent of the DB session.
    """

    priority: str = "medium"
    impact: str = "medium"
    confidence: float = 0.5
    start_offset: int = 0
    end_offset: int = 0


class TestVerdictForComments:
    def test_no_comments_is_clean(self) -> None:
        assert _verdict_for_comments([]) == "clean"

    def test_single_medium_comment_is_review_needed(self) -> None:
        assert _verdict_for_comments([FakeComment(priority="medium")]) == "review_needed"

    def test_single_critical_comment_is_problems(self) -> None:
        assert _verdict_for_comments([FakeComment(priority="critical")]) == "problems"

    def test_two_high_priority_comments_escalate_to_problems(self) -> None:
        comments = [
            FakeComment(priority="high", impact="medium", confidence=0.5),
            FakeComment(priority="high", impact="medium", confidence=0.5),
        ]
        assert _verdict_for_comments(comments) == "problems"

    def test_single_high_priority_with_medium_impact_stays_review_needed(self) -> None:
        # One high-priority / medium-impact comment is not enough to block.
        comments = [FakeComment(priority="high", impact="medium", confidence=0.5)]
        assert _verdict_for_comments(comments) == "review_needed"

    def test_single_high_impact_high_confidence_escalates_to_problems(self) -> None:
        # High priority + high impact + high confidence = problems even if alone.
        comments = [FakeComment(priority="high", impact="high", confidence=0.85)]
        assert _verdict_for_comments(comments) == "problems"

    def test_single_high_impact_low_confidence_stays_review_needed(self) -> None:
        # High priority + high impact but low confidence should not block.
        comments = [FakeComment(priority="high", impact="high", confidence=0.6)]
        assert _verdict_for_comments(comments) == "review_needed"

    def test_many_low_priority_comments_stay_review_needed(self) -> None:
        # Pure volume without severity is not enough to trip `problems`.
        comments = [FakeComment(priority="low") for _ in range(20)]
        assert _verdict_for_comments(comments) == "review_needed"


class TestCleanStatement:
    def test_clean_verdict_uses_whole_document_copy(self) -> None:
        assert _clean_statement("clean", []) == (
            "Entire document is clean — no significant issues found."
        )

    def test_single_clean_section_is_named(self) -> None:
        assert (
            _clean_statement("review_needed", ["Introduction"])
            == "Introduction is clean — no issues found."
        )

    def test_two_clean_sections_use_and(self) -> None:
        assert _clean_statement("review_needed", ["A", "B"]) == (
            "A and B are clean — no issues found."
        )

    def test_many_clean_sections_truncate_with_remainder(self) -> None:
        assert _clean_statement(
            "review_needed", ["A", "B", "C", "D", "E"]
        ) == "A, B, C, and 2 more are clean — no issues found."

    def test_no_clean_sections_message_is_explicit(self) -> None:
        assert (
            _clean_statement("review_needed", [])
            == "No section is clean enough to skip yet."
        )


class TestCleanSectionsForComments:
    def test_section_with_no_overlapping_comments_is_clean(self) -> None:
        content = "# Intro\n\nHello world.\n\n# Body\n\nSome detailed body text here.\n"
        sections = _build_sections(content)
        # A comment anchored only in the Body keeps Intro clean.
        body_start = content.index("# Body")
        comment = FakeComment(start_offset=body_start + 10, end_offset=body_start + 20)
        clean = _clean_sections_for_comments(sections, [comment])
        assert "Intro" in clean
        assert "Body" not in clean

    def test_section_with_overlapping_comment_is_not_clean(self) -> None:
        content = "# Intro\n\nHello world.\n"
        sections = _build_sections(content)
        # Comment spanning the Intro body should mark it as not-clean.
        comment = FakeComment(start_offset=10, end_offset=15)
        clean = _clean_sections_for_comments(sections, [comment])
        assert clean == []

    def test_empty_sections_list_produces_no_clean_sections(self) -> None:
        assert _clean_sections_for_comments([], [FakeComment()]) == []


class TestLocationLabel:
    def test_offset_inside_section_paragraph_names_the_section(self) -> None:
        content = "# Intro\n\nFirst paragraph here.\n\nSecond paragraph here.\n"
        sections = _build_sections(content)
        para2_start = content.index("Second paragraph")
        label = _location_label(sections, para2_start, para2_start + 5)
        assert "Intro" in label
        assert "paragraph" in label.lower()

    def test_offset_outside_any_section_falls_back_to_raw_offsets(self) -> None:
        label = _location_label([], 7, 42)
        assert label == "Offsets 7-42"


@pytest.mark.parametrize(
    "comments,expected",
    [
        ([], "clean"),
        ([FakeComment(priority="low")], "review_needed"),
        ([FakeComment(priority="medium"), FakeComment(priority="medium")], "review_needed"),
        ([FakeComment(priority="critical")], "problems"),
    ],
)
def test_verdict_parametrized_boundaries(comments, expected) -> None:
    assert _verdict_for_comments(comments) == expected
