#!/usr/bin/env bash
set -euo pipefail

# Bootstraps labels + milestones for OpinionatedDocReviewer.
# Safe defaults:
# - Dry-run by default (prints commands)
# - Idempotent label upserts via --force
# - Milestones are created if missing, patched if present

APPLY=0
REPO="${GH_REPO:-}"

usage() {
  cat <<'USAGE'
Usage:
  bootstrap-labels-milestones.sh [--apply] [--repo owner/name]

Options:
  --apply              Execute gh commands (default is dry-run/print only)
  --repo owner/name    Target repository (default: current gh repo view or GH_REPO env)
  -h, --help           Show this help

Examples:
  ./scripts/github/bootstrap-labels-milestones.sh
  ./scripts/github/bootstrap-labels-milestones.sh --apply
  ./scripts/github/bootstrap-labels-milestones.sh --apply --repo acme/opinionated-doc-reviewer
USAGE
}

manual_fallback() {
  cat <<'FALLBACK'
gh CLI is unavailable (or not authenticated). Use manual setup in GitHub UI:

1) Labels:
   - Repository -> Settings -> Labels
   - Create labels listed in:
     /home/zob/src/OpinionatedDocReviewer/docs/process/github-project-bootstrap-checklist.md

2) Milestones:
   - Repository -> Issues -> Milestones
   - Create milestones M1..M4 listed in:
     /home/zob/src/OpinionatedDocReviewer/docs/process/github-project-bootstrap-checklist.md

3) Continue project setup with:
   /home/zob/src/OpinionatedDocReviewer/docs/process/github-project-bootstrap-checklist.md
FALLBACK
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      APPLY=1
      ;;
    --repo)
      if [[ $# -lt 2 ]]; then
        echo "error: --repo requires owner/name" >&2
        exit 1
      fi
      REPO="$2"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument '$1'" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if ! command -v gh >/dev/null 2>&1; then
  manual_fallback
  exit 0
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "gh CLI found, but not authenticated." >&2
  manual_fallback
  exit 0
fi

if [[ -z "$REPO" ]]; then
  if ! REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null)"; then
    echo "error: unable to resolve repository. Pass --repo owner/name or set GH_REPO." >&2
    exit 1
  fi
fi

run_or_print() {
  if [[ "$APPLY" -eq 1 ]]; then
    "$@"
  else
    printf '+'
    for arg in "$@"; do
      printf ' %q' "$arg"
    done
    printf '\n'
  fi
}

ensure_label() {
  local name="$1"
  local color="$2"
  local description="$3"
  run_or_print gh label create "$name" --repo "$REPO" --color "$color" --description "$description" --force
}

lookup_milestone_number() {
  local title="$1"
  gh api "repos/${REPO}/milestones?state=all&per_page=100" \
    --jq ".[] | select(.title == \"${title}\") | .number" 2>/dev/null | head -n1 || true
}

ensure_milestone() {
  local title="$1"
  local due_on="$2"
  local description="$3"

  local milestone_number
  milestone_number="$(lookup_milestone_number "$title")"

  if [[ -n "$milestone_number" ]]; then
    run_or_print gh api --method PATCH "repos/${REPO}/milestones/${milestone_number}" \
      -f "title=${title}" \
      -f "description=${description}" \
      -f "due_on=${due_on}"
  else
    run_or_print gh api --method POST "repos/${REPO}/milestones" \
      -f "title=${title}" \
      -f "description=${description}" \
      -f "due_on=${due_on}"
  fi
}

echo "Target repository: ${REPO}"
if [[ "$APPLY" -eq 0 ]]; then
  echo "Mode: dry-run (printing commands). Re-run with --apply to execute."
else
  echo "Mode: apply (executing commands)."
fi

declare -a LABELS=(
  "type:feature|0E8A16|New functionality"
  "type:bug|D73A4A|Bug fix"
  "type:refactor|5319E7|Internal code restructuring"
  "type:docs|0075CA|Documentation updates"
  "type:test|FBCA04|Test additions or fixes"
  "type:security|B60205|Security hardening or remediation"
  "type:ops|1D76DB|Operations and environment changes"
  "type:spike|C2E0C6|Timeboxed research/prototyping"

  "area:backend|1F6FEB|Backend APIs and services"
  "area:frontend|A371F7|Frontend UX and components"
  "area:review-engine|0B7285|Review orchestration and workers"
  "area:meta-critic|C5DEF5|Meta synthesis and directives"
  "area:auth|6F42C1|Authentication and authorization"
  "area:security|B60205|Security controls"
  "area:infra|0052CC|Infrastructure and deployment"
  "area:ci|0B7285|CI/CD workflows"
  "area:docs|0366D6|Documentation"

  "prio:p0|B60205|Highest priority"
  "prio:p1|D93F0B|High priority"
  "prio:p2|FBCA04|Medium priority"
  "prio:p3|0E8A16|Lower priority"

  "state:ready|0E8A16|Ready to start"
  "state:in-progress|1D76DB|Work in progress"
  "state:needs-review|5319E7|Awaiting review"
  "state:blocked|000000|Blocked by dependency/decision"
  "state:needs-info|FBCA04|Needs clarification"
  "state:do-not-merge|B60205|Hard merge block"

  "risk:high|B60205|High risk"
  "risk:medium|D93F0B|Medium risk"
  "risk:low|0E8A16|Low risk"
  "impact:customer|7F52FF|Direct customer impact"
  "impact:platform|5319E7|Platform/internal impact"

  "size:xs|C2E0C6|Extra small"
  "size:s|BFDADC|Small"
  "size:m|FEF2C0|Medium"
  "size:l|F9D0C4|Large"
  "size:xl|E4E669|Extra large"
)

declare -a MILESTONES=(
  "M1 Meta-first UX + synthesis orchestration|2026-03-27T23:59:59Z|Meta-first default UX and reliable synthesis orchestration for release v0.2.0-m1."
  "M2 Persona contract reliability|2026-04-24T23:59:59Z|Harden persona prompt/output contract reliability with regression coverage."
  "M3 Platform hardening|2026-05-22T23:59:59Z|Security/auth/observability hardening for multi-tenant trust."
  "M4 Delivery throughput + API-boundary maturity|2026-06-19T23:59:59Z|Frontend decomposition, CI gates, and API-boundary maturity."
)

echo
echo "Ensuring labels..."
for entry in "${LABELS[@]}"; do
  IFS='|' read -r name color description <<< "$entry"
  ensure_label "$name" "$color" "$description"
done

echo
echo "Ensuring milestones..."
for entry in "${MILESTONES[@]}"; do
  IFS='|' read -r title due_on description <<< "$entry"
  ensure_milestone "$title" "$due_on" "$description"
done

echo
echo "Bootstrap complete."
echo "Next manual steps:"
echo "- Configure required checks and branch protection (see /home/zob/src/OpinionatedDocReviewer/docs/process/github-project-bootstrap-checklist.md)."
echo "- Create GitHub Project v2 fields/views and seed M1 issues."
