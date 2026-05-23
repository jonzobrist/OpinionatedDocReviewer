"""Tests for the LLM-synthesized verdict path in meta_reviews.

Exercises the three flows:
1. Happy path — LLM returns a valid JSON contract → summary gets
   bottom_line + top_blockers + synthesized_by_llm=True.
2. Provider failure — generate_completion raises → summary falls back to
   the rule-based verdict with bottom_line=None and
   synthesized_by_llm=False.
3. Malformed response — LLM returns garbage or wrong verdict token → same
   graceful fallback as (2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json

import pytest

from app.api import meta_reviews as meta_reviews_api
from app.core.config import settings


@dataclass
class FakeSource:
    comment_id: int = 1


@dataclass
class FakeMetaComment:
    id: int
    content: str
    priority: str = "high"
    impact: str = "medium"
    confidence: float = 0.7
    start_offset: int = 0
    end_offset: int = 10
    sources: list[FakeSource] = field(default_factory=list)


@dataclass
class FakeRun:
    status: str = "completed"
    comments: list[FakeMetaComment] = field(default_factory=list)


def _comment(id_: int = 1, priority: str = "high") -> FakeMetaComment:
    return FakeMetaComment(
        id=id_,
        content=f"Comment {id_} raises a concern worth acting on.",
        priority=priority,
        impact="high",
        confidence=0.85,
        sources=[FakeSource(comment_id=id_ * 100)],
    )


@pytest.fixture(autouse=True)
def _enable_llm_verdict(monkeypatch):
    # The shared conftest disables LLM verdict by default; re-enable it
    # for the tests in this module so we exercise the LLM path directly.
    monkeypatch.setattr(settings, "META_VERDICT_USE_LLM", True)


def test_happy_path_llm_verdict_populates_bottom_line_and_blockers(monkeypatch):
    llm_json = json.dumps(
        {
            "verdict": "problems",
            "bottom_line": "Ship-blocking security claim in section 2 is unverified.",
            "top_blockers": [
                "Unverified token validation rule",
                "Missing rate-limit numbers",
            ],
        }
    )
    monkeypatch.setattr(meta_reviews_api, "generate_completion", lambda _: llm_json)

    run = FakeRun(comments=[_comment(1), _comment(2, priority="medium")])
    payload = meta_reviews_api._build_summary_payload(run, content="# Intro\n\nBody paragraph.")

    assert payload is not None
    assert payload["verdict"] == "problems"
    assert payload["bottom_line"] == "Ship-blocking security claim in section 2 is unverified."
    assert payload["top_blockers"] == [
        "Unverified token validation rule",
        "Missing rate-limit numbers",
    ]
    assert payload["synthesized_by_llm"] is True
    # Deterministic surfaces still come from the helpers.
    assert len(payload["attention_points"]) == 2
    assert payload["attention_points"][0]["meta_comment_id"] == 1


def test_provider_error_falls_back_to_rule_based_verdict(monkeypatch):
    from app.reviews.llm_provider import LLMProviderError

    def fail(_prompt: str) -> str:
        raise LLMProviderError("provider down")

    monkeypatch.setattr(meta_reviews_api, "generate_completion", fail)

    # One high-priority / high-impact / high-confidence comment → rule
    # classifies as problems (see _verdict_for_comments).
    run = FakeRun(comments=[_comment(1)])
    payload = meta_reviews_api._build_summary_payload(run, content="Body.")

    assert payload is not None
    assert payload["verdict"] == "problems"
    assert payload["bottom_line"] is None
    assert payload["top_blockers"] == []
    assert payload["synthesized_by_llm"] is False


def test_malformed_json_response_falls_back(monkeypatch):
    monkeypatch.setattr(
        meta_reviews_api,
        "generate_completion",
        lambda _: "this is not json at all",
    )

    run = FakeRun(comments=[_comment(1, priority="medium")])
    payload = meta_reviews_api._build_summary_payload(run, content="Body.")

    assert payload is not None
    # One medium-priority comment → rule verdict is review_needed.
    assert payload["verdict"] == "review_needed"
    assert payload["bottom_line"] is None
    assert payload["synthesized_by_llm"] is False


def test_invalid_verdict_token_falls_back(monkeypatch):
    monkeypatch.setattr(
        meta_reviews_api,
        "generate_completion",
        lambda _: json.dumps({"verdict": "meh", "bottom_line": "bad", "top_blockers": []}),
    )

    run = FakeRun(comments=[_comment(1)])
    payload = meta_reviews_api._build_summary_payload(run, content="Body.")

    assert payload is not None
    assert payload["synthesized_by_llm"] is False


def test_flag_disabled_skips_llm_path(monkeypatch):
    # When META_VERDICT_USE_LLM is False the LLM code path must not be
    # invoked at all — i.e. generate_completion should not be called.
    monkeypatch.setattr(settings, "META_VERDICT_USE_LLM", False)
    call_count = {"n": 0}

    def counting(_prompt: str) -> str:
        call_count["n"] += 1
        return "{}"

    monkeypatch.setattr(meta_reviews_api, "generate_completion", counting)

    run = FakeRun(comments=[_comment(1)])
    payload = meta_reviews_api._build_summary_payload(run, content="Body.")

    assert payload is not None
    assert payload["synthesized_by_llm"] is False
    assert call_count["n"] == 0


def test_response_wrapped_in_markdown_fence_is_still_parsed(monkeypatch):
    fenced = "```json\n" + json.dumps(
        {
            "verdict": "review_needed",
            "bottom_line": "Tighten phrasing in section 1.",
            "top_blockers": [],
        }
    ) + "\n```"
    monkeypatch.setattr(meta_reviews_api, "generate_completion", lambda _: fenced)

    run = FakeRun(comments=[_comment(1, priority="medium")])
    payload = meta_reviews_api._build_summary_payload(run, content="Body.")

    assert payload is not None
    assert payload["verdict"] == "review_needed"
    assert payload["bottom_line"] == "Tighten phrasing in section 1."
    assert payload["synthesized_by_llm"] is True


def test_empty_comments_short_circuits_to_rule_clean_verdict(monkeypatch):
    # LLM path should not be hit when there are no comments — the rule
    # helper already returns "clean" deterministically.
    call_count = {"n": 0}

    def counting(_prompt: str) -> str:
        call_count["n"] += 1
        return "{}"

    monkeypatch.setattr(meta_reviews_api, "generate_completion", counting)

    run = FakeRun(comments=[])
    payload = meta_reviews_api._build_summary_payload(run, content="Body.")

    assert payload is not None
    assert payload["verdict"] == "clean"
    assert payload["synthesized_by_llm"] is False
    assert call_count["n"] == 0
