from __future__ import annotations

from dataclasses import dataclass

from app.db import models

PERM_RANK = {"viewer": 1, "editor": 2, "owner": 3}


@dataclass
class PolicyEvalResult:
    denied: bool
    allow_level: str | None
    matched_ids: list[int]
    reason: str


def action_for_minimum(minimum: str) -> str:
    if minimum == "viewer":
        return "document.read"
    if minimum == "editor":
        return "document.write"
    return "document.owner"


def _tags(value: list | None) -> set[str]:
    if not value:
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _matches_conditions(
    policy: models.ResourcePolicy,
    user: models.User,
    document: models.Document | None,
) -> bool:
    cond = policy.conditions or {}
    roles_any = _tags(cond.get("roles_any"))
    if roles_any and user.role not in roles_any:
        return False

    user_tags_any = _tags(cond.get("user_tags_any"))
    user_tags = _tags(user.tags)
    if user_tags_any and not (user_tags & user_tags_any):
        return False

    doc_tags_any = _tags(cond.get("document_tags_any"))
    doc_tags = _tags(document.tags if document else [])
    if doc_tags_any and not (doc_tags & doc_tags_any):
        return False

    return True


def evaluate_document_policies(
    *,
    policies: list[models.ResourcePolicy],
    user: models.User,
    document: models.Document | None,
) -> PolicyEvalResult:
    deny_hits: list[models.ResourcePolicy] = []
    allow_hits: list[models.ResourcePolicy] = []

    for policy in policies:
        if policy.resource_id is not None and (not document or policy.resource_id != document.id):
            continue
        if not _matches_conditions(policy, user, document):
            continue
        if policy.effect == "deny":
            deny_hits.append(policy)
        elif policy.effect == "allow":
            allow_hits.append(policy)

    if deny_hits:
        return PolicyEvalResult(
            denied=True,
            allow_level=None,
            matched_ids=[item.id for item in deny_hits],
            reason="explicit deny policy matched",
        )

    strongest = None
    strongest_rank = 0
    matched_ids: list[int] = []
    for item in allow_hits:
        matched_ids.append(item.id)
        level = str((item.conditions or {}).get("permission_level", "viewer"))
        rank = PERM_RANK.get(level, 0)
        if rank > strongest_rank:
            strongest_rank = rank
            strongest = level
    return PolicyEvalResult(
        denied=False,
        allow_level=strongest,
        matched_ids=matched_ids,
        reason="allow policy matched" if strongest else "no policy match",
    )
