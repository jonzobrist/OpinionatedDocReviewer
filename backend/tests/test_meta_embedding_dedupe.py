"""Tests for the embedding-based dedupe path in meta_reviewer.

Token-Jaccard misses semantic duplicates like "improve clarity of
section 3" vs. "section 3 needs clearer writing" — they share few
tokens. Embeddings close that gap when the provider is available,
while preserving the Jaccard fallback for air-gapped / degraded
deployments.
"""

from __future__ import annotations

from math import sqrt

import pytest

from app.core.config import settings
from app.reviews import meta_reviewer
from app.reviews.meta_reviewer import (
    MetaDirectiveCandidate,
    _cosine_similarity,
    dedupe_directives,
)


def _candidate(
    content: str,
    *,
    category: str = "clarity",
    priority: str = "medium",
    start_offset: int = 0,
    end_offset: int = 50,
    order_index: int = 0,
    rank_score: float = 1.0,
) -> MetaDirectiveCandidate:
    return MetaDirectiveCandidate(
        content=content,
        category=category,
        priority=priority,
        impact="medium",
        effort="medium",
        confidence=0.7,
        why_now=None,
        recommended_change=None,
        verification_step=None,
        status="open",
        assignee=None,
        due_at=None,
        rank_score=rank_score,
        start_offset=start_offset,
        end_offset=end_offset,
        order_index=order_index,
        contributing_reviewers=[],
        source_comments=[],
        is_unsynthesized=False,
    )


def _unit(v: list[float]) -> list[float]:
    norm = sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm else v


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert _cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self) -> None:
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_empty_inputs_are_safe(self) -> None:
        assert _cosine_similarity([], [1.0]) == 0.0
        assert _cosine_similarity([1.0], []) == 0.0

    def test_length_mismatch_returns_zero(self) -> None:
        assert _cosine_similarity([1.0, 2.0], [1.0]) == 0.0


class TestDedupeEmbeddingPath:
    def test_semantically_similar_directives_merge_under_embeddings(self, monkeypatch) -> None:
        """Two directives that share meaning but not tokens should merge
        when embeddings say they are the same thing.

        With Jaccard these would survive as duplicates because the
        0.72 threshold requires heavy token overlap.
        """
        monkeypatch.setattr(settings, "META_DEDUPE_USE_EMBEDDINGS", True)

        # Vectors chosen so the two content strings are ~0.99 cosine —
        # clearly above the 0.85 embedding threshold — while having
        # near-zero token overlap in their content strings.
        vec_a = _unit([1.0, 0.1, 0.05])
        vec_b = _unit([0.99, 0.11, 0.06])

        monkeypatch.setattr(
            meta_reviewer,
            "generate_embeddings",
            lambda texts: [vec_a, vec_b],
        )

        first = _candidate(
            "Section 3 prose density overwhelms the reader.",
            start_offset=100,
            end_offset=200,
            order_index=0,
        )
        second = _candidate(
            "Loosen up the middle body — too dense for casual reading.",
            start_offset=110,
            end_offset=210,
            order_index=1,
        )

        result = dedupe_directives([first, second])

        assert len(result) == 1, "semantically identical directives must merge"

    def test_semantically_distinct_directives_stay_separate(self, monkeypatch) -> None:
        """Two directives on different topics should remain as two
        separate meta comments even when they share a section.
        """
        monkeypatch.setattr(settings, "META_DEDUPE_USE_EMBEDDINGS", True)

        # Orthogonal embeddings — low cosine.
        monkeypatch.setattr(
            meta_reviewer,
            "generate_embeddings",
            lambda texts: [_unit([1.0, 0.0, 0.0]), _unit([0.0, 1.0, 0.0])],
        )

        first = _candidate(
            "Clarify the API authentication policy.",
            category="technical",
            start_offset=0,
            end_offset=50,
            order_index=0,
        )
        second = _candidate(
            "Add a typography guideline to the style section.",
            category="style",
            start_offset=0,
            end_offset=50,
            order_index=1,
        )

        result = dedupe_directives([first, second])

        assert len(result) == 2


class TestDedupeFallback:
    def test_embedding_provider_failure_falls_back_to_jaccard(self, monkeypatch) -> None:
        """When the embedding provider raises, dedupe must not crash —
        it falls back to the existing Jaccard path so pipelines in
        air-gapped / degraded environments still produce output.
        """
        from app.reviews.llm_provider import LLMProviderError

        monkeypatch.setattr(settings, "META_DEDUPE_USE_EMBEDDINGS", True)

        def failing(_texts: list[str]) -> list[list[float]]:
            raise LLMProviderError("provider down")

        monkeypatch.setattr(meta_reviewer, "generate_embeddings", failing)

        # Two heavy token-overlap directives would merge under Jaccard
        # at the 0.72 threshold — proves we actually ran the fallback.
        # Content chosen so Jaccard similarity is clearly above 0.72
        # (4/5 tokens shared = 0.8 Jaccard → 0.56 text-weighted + 0.2
        # near + 0.1 category = 0.86 > 0.72).
        first = _candidate(
            "Clarify opening paragraph introduction.",
            start_offset=0,
            end_offset=60,
            order_index=0,
        )
        second = _candidate(
            "Clarify opening paragraph introduction clearly.",
            start_offset=0,
            end_offset=60,
            order_index=1,
        )

        result = dedupe_directives([first, second])

        assert len(result) == 1

    def test_feature_flag_off_uses_jaccard(self, monkeypatch) -> None:
        call_count = {"n": 0}

        def counting(_texts: list[str]) -> list[list[float]]:
            call_count["n"] += 1
            return []

        monkeypatch.setattr(settings, "META_DEDUPE_USE_EMBEDDINGS", False)
        monkeypatch.setattr(meta_reviewer, "generate_embeddings", counting)

        first = _candidate("The opening paragraph confuses the reader.", order_index=0)
        second = _candidate("The opening paragraph feels unclear to readers.", order_index=1)

        dedupe_directives([first, second])

        assert call_count["n"] == 0

    def test_empty_embedding_for_blank_content_does_not_crash(self, monkeypatch) -> None:
        """If the provider returns an empty vector for a candidate we
        skip pairwise embedding checks for that candidate rather than
        treating the empty vector as "similar to everything".
        """
        monkeypatch.setattr(settings, "META_DEDUPE_USE_EMBEDDINGS", True)

        # Both non-empty so the path stays on embeddings; first vector
        # is aligned with second so they should merge, third is empty
        # (bad input) which falls back to Jaccard for its comparisons.
        monkeypatch.setattr(
            meta_reviewer,
            "generate_embeddings",
            lambda texts: [_unit([1.0, 0.1]), _unit([0.99, 0.12]), []],
        )

        first = _candidate("Tighten the intro.", order_index=0)
        second = _candidate("Make the intro crisper.", order_index=1)
        third = _candidate(
            "Wholly unrelated direction about the appendix footer styling.",
            start_offset=1000,
            end_offset=1100,
            category="style",
            order_index=2,
        )

        result = dedupe_directives([first, second, third])

        # First two merge, third stays separate — no crash on the empty
        # embedding for the third candidate.
        assert len(result) == 2
