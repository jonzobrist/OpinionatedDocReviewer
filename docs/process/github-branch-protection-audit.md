# GitHub Branch Protection Audit (main)

Generated: 2026-03-03 02:16 UTC
Repository: `jonzobrist/OpinionatedDocReviewer`
Branch: `main`

## Objective

Configure GitHub Free-compatible branch-protection-lite on `main` with PR+review gates, conversation resolution, force-push/deletion guards, and required CI/security checks.

## Evidence commands (executed)

```bash
gh api repos/jonzobrist/OpinionatedDocReviewer/branches/main/protection
gh api repos/jonzobrist/OpinionatedDocReviewer/rulesets
gh api repos/jonzobrist/OpinionatedDocReviewer/commits/5dc7a058ca41689d0c24e884fe63d83d21239a0a/check-runs
gh api --method PUT repos/jonzobrist/OpinionatedDocReviewer/branches/main/protection --input /tmp/main_protection_payload.json
```

## Before status

- Branch protection: **not enabled** (API returned 404).
- API evidence: `gh: Branch not protected (HTTP 404)`
- Repo rulesets configured: `0`

## Check-context discovery

- Main HEAD SHA inspected: `5dc7a058ca41689d0c24e884fe63d83d21239a0a`
- Available check run names: `Dependabot, backend, backend-audit, dependency-review, frontend, frontend-audit`

| Checklist target check | Applied required context | Resolution mode |
|---|---|---|
| `CI / backend` | `backend` | `fallback-short-name` |
| `CI / frontend` | `frontend` | `fallback-short-name` |
| `Security Scan / dependency-review` | `dependency-review` | `fallback-short-name` |
| `Security Scan / backend-audit` | `backend-audit` | `fallback-short-name` |
| `Security Scan / frontend-audit` | `frontend-audit` | `fallback-short-name` |

> Note: this repository exposes GitHub Actions required-check contexts as short job names (`backend`, `frontend`, etc.), so those were used as exact enforceable contexts.

## Applied configuration

- Apply operation: **success**
- Require pull requests before merge: **enabled** (via required PR reviews)
- Required approving reviews: `1`
- Dismiss stale reviews: `False`
- Require conversation resolution: `True`
- Allow force pushes: `False`
- Allow deletions: `False`
- Required status checks: `backend, backend-audit, dependency-review, frontend, frontend-audit`
- Strict status checks (up-to-date branch required): `True`

## After status

- Branch protection: **enabled**
- Required approving reviews: `1`
- Dismiss stale reviews: `False`
- Conversation resolution required: `True`
- Allow force pushes: `False`
- Allow deletions: `False`
- Required checks: `backend, backend-audit, dependency-review, frontend, frontend-audit`
- Repo rulesets configured: `0`

## Manual follow-up / limitations

- No blocking GitHub Free/tier limitation encountered for requested branch-protection-lite settings.
- Optional manual follow-up: in GitHub UI, verify branch protection on `main` under Settings → Branches for visibility/audit trail.

## Reversibility

To modify or remove protection later (maintainer/admin only):
```bash
# View current protection
gh api repos/jonzobrist/OpinionatedDocReviewer/branches/main/protection
# Remove protection entirely (use with caution)
gh api --method DELETE repos/jonzobrist/OpinionatedDocReviewer/branches/main/protection
```

## Update: CODEOWNER review requirement enabled (2026-03-03 02:20 UTC)

### Change summary
- Previous setting: `required_pull_request_reviews.require_code_owner_reviews = false`
- Updated setting: `required_pull_request_reviews.require_code_owner_reviews = true`
- Existing protections preserved (not weakened):
  - required approvals: `1`
  - dismiss stale reviews: `false`
  - required conversation resolution: `true`
  - force pushes allowed: `false`
  - deletions allowed: `false`
  - required checks: `backend`, `frontend`, `dependency-review`, `backend-audit`, `frontend-audit`

### Evidence
```bash
# Apply CODEOWNER review requirement
gh api --method PATCH repos/jonzobrist/OpinionatedDocReviewer/branches/main/protection/required_pull_request_reviews \
  -F dismiss_stale_reviews=false \
  -F require_code_owner_reviews=true \
  -F required_approving_review_count=1 \
  -F require_last_push_approval=false

# Verify
gh api repos/jonzobrist/OpinionatedDocReviewer/branches/main/protection --jq '{required_pull_request_reviews: .required_pull_request_reviews, required_status_checks: .required_status_checks.contexts, required_conversation_resolution: .required_conversation_resolution.enabled, allow_force_pushes: .allow_force_pushes.enabled, allow_deletions: .allow_deletions.enabled}'
```

### Operational note
- CODEOWNERS placeholder handles were replaced with `@jonzobrist` to make CODEOWNER review enforcement effective immediately.
- Follow-up: split ownership by area/team once long-term maintainers are confirmed.
