from __future__ import annotations

from typing import Iterable

from app.reviews.parsing import CANONICAL_VIOLATION_TAXONOMY, normalize_comment_output_metadata


def build_empty_review_quality_telemetry() -> dict:
    return {
        "total_comments": 0,
        "fallback_count": 0,
        "truncated_count": 0,
        "violation_count_by_type": _empty_violation_counts(),
        "per_persona": {},
    }


def normalize_review_quality_telemetry(telemetry: dict | None) -> dict:
    normalized = build_empty_review_quality_telemetry()
    if not isinstance(telemetry, dict):
        return normalized

    normalized["total_comments"] = _coerce_non_negative_int(telemetry.get("total_comments"))
    normalized["fallback_count"] = _coerce_non_negative_int(telemetry.get("fallback_count"))
    normalized["truncated_count"] = _coerce_non_negative_int(telemetry.get("truncated_count"))
    normalized["violation_count_by_type"] = _normalize_violation_count_map(telemetry.get("violation_count_by_type"))

    raw_per_persona = telemetry.get("per_persona")
    if isinstance(raw_per_persona, dict):
        for key, value in raw_per_persona.items():
            persona_id = _coerce_optional_int(value.get("persona_id") if isinstance(value, dict) else None)
            if persona_id is None:
                persona_id = _coerce_optional_int(key)
            persona_key = str(persona_id) if persona_id is not None else str(key)
            normalized["per_persona"][persona_key] = _normalize_persona_bucket(value, persona_id)

    return normalized


def build_review_quality_telemetry_from_entries(
    entries: Iterable[tuple[int | None, dict | None, dict | None]],
) -> dict:
    telemetry = build_empty_review_quality_telemetry()

    for persona_id, output_metadata, output_requirements in entries:
        metadata = normalize_comment_output_metadata(output_metadata, output_requirements)
        _increment_bucket(telemetry, metadata)

        persona_key = str(persona_id) if persona_id is not None else "unknown"
        bucket = telemetry["per_persona"].setdefault(
            persona_key,
            _empty_persona_bucket(persona_id),
        )
        _increment_bucket(bucket, metadata)

    return telemetry


def _normalize_persona_bucket(value: object, persona_id: int | None) -> dict:
    if not isinstance(value, dict):
        value = {}
    return {
        "persona_id": persona_id,
        "total_comments": _coerce_non_negative_int(value.get("total_comments")),
        "fallback_count": _coerce_non_negative_int(value.get("fallback_count")),
        "truncated_count": _coerce_non_negative_int(value.get("truncated_count")),
        "violation_count_by_type": _normalize_violation_count_map(value.get("violation_count_by_type")),
    }


def _empty_violation_counts() -> dict[str, int]:
    return {name: 0 for name in CANONICAL_VIOLATION_TAXONOMY}


def _empty_persona_bucket(persona_id: int | None) -> dict:
    return {
        "persona_id": persona_id,
        "total_comments": 0,
        "fallback_count": 0,
        "truncated_count": 0,
        "violation_count_by_type": _empty_violation_counts(),
    }


def _increment_bucket(bucket: dict, metadata: dict) -> None:
    bucket["total_comments"] += 1
    if metadata.get("used_fallback"):
        bucket["fallback_count"] += 1
    if metadata.get("truncated"):
        bucket["truncated_count"] += 1

    counts = bucket["violation_count_by_type"]
    for violation in metadata.get("violations") or []:
        if violation not in counts:
            counts[violation] = 0
        counts[violation] += 1


def _normalize_violation_count_map(value: object) -> dict[str, int]:
    counts = _empty_violation_counts()
    if not isinstance(value, dict):
        return counts

    for key, raw_count in value.items():
        token = str(key).strip()
        if not token:
            continue
        counts[token] = _coerce_non_negative_int(raw_count)
    return counts


def _coerce_non_negative_int(value: object) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    if parsed < 0:
        return 0
    return parsed


def _coerce_optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
