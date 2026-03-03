# GitHub Free Work Management Model for OpinionatedDocReviewer

Last updated: 2026-03-01

## Scope
This model uses only **GitHub Free-compatible** capabilities (Issues, Milestones, Projects, Actions, templates, CODEOWNERS, basic branch governance).

Reference artifacts in this repo:
- CI workflow: [`/home/zob/src/OpinionatedDocReviewer/.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
- Security workflow: [`/home/zob/src/OpinionatedDocReviewer/.github/workflows/security-scan.yml`](../../.github/workflows/security-scan.yml)
- Engineering standard: [`/home/zob/src/OpinionatedDocReviewer/AGENTS.md`](../../AGENTS.md)
- Product theory: [`/home/zob/src/OpinionatedDocReviewer/THEORY.MD`](../../THEORY.MD)

---

## 1) Operating model (free tier)

## Core objects
- **Issues** = single unit of planned work.
- **Milestones** = timeboxed execution goals (map to M1/M2/M3/M4).
- **Project (v2)** = source of truth for status and flow.
- **Pull Requests** = implementation and review record tied to issue(s).
- **Releases** = versioned user-facing change summaries.

## Roles
- **Manager/maintainer:** triage, prioritize, assign, enforce definitions of done.
- **Contributor/agent:** implements one scoped issue per PR.
- **Reviewer/CODEOWNER:** validates correctness/security/docs before merge.

---

## 2) Labels: recommended taxonomy

Use prefixed labels to keep filtering predictable.

### Type labels (required, exactly one)
- `type:feature`
- `type:bug`
- `type:refactor`
- `type:docs`
- `type:test`
- `type:security`
- `type:ops`
- `type:spike`

### Area labels (required, 1-2 max)
- `area:backend`
- `area:frontend`
- `area:review-engine`
- `area:meta-critic`
- `area:auth`
- `area:security`
- `area:infra`
- `area:ci`
- `area:docs`

### Priority labels (required, exactly one)
- `prio:p0`
- `prio:p1`
- `prio:p2`
- `prio:p3`

### Status/support labels (optional)
- `state:blocked`
- `state:needs-info`
- `state:ready`
- `state:in-progress`
- `state:needs-review`
- `state:do-not-merge`

### Risk/impact labels (optional)
- `risk:high`
- `risk:medium`
- `risk:low`
- `impact:customer`
- `impact:platform`

---

## 3) Milestones

Create milestones aligned to the execution plan:
- `M1 Meta-first UX + synthesis orchestration`
- `M2 Persona contract reliability`
- `M3 Platform hardening`
- `M4 Delivery throughput + API-boundary maturity`

Milestone description should include:
- objective
- exit criteria
- target date
- explicit validation commands

---

## 4) Project board (GitHub Projects v2)

Create one project: **"ODR Delivery Board"**

### Recommended custom fields
- `Status` (Todo, Ready, In Progress, In Review, Blocked, Done)
- `Priority` (P0/P1/P2/P3)
- `Type` (Feature/Bug/Refactor/Docs/Test/Security/Ops/Spike)
- `Area` (Backend/Frontend/Meta/Auth/Security/CI/Docs)
- `Milestone` (M1/M2/M3/M4)
- `Size` (XS/S/M/L/XL)
- `Owner` (GitHub assignee)
- `Target Date` (date)
- `Risk` (Low/Medium/High)

### Views to create
1. **Backlog by Priority** (group by Priority)
2. **Current Milestone Kanban** (filter by active milestone, group by Status)
3. **By Area** (group by Area)
4. **Review Queue** (Status=In Review)
5. **Blocked** (Status=Blocked or label `state:blocked`)
6. **Done This Week** (Status=Done + updated within 7 days)

---

## 5) Issue templates (free, high leverage)

Add under `.github/ISSUE_TEMPLATE/`:
- `feature.yml`
- `bug.yml`
- `security.yml`
- `spike.yml`
- `ops.yml`

Each template should require:
- Problem statement
- Scope boundaries (explicit non-goals)
- Acceptance criteria (checklist)
- Validation commands
- Risk notes
- Docs impact
- Related milestone + labels

Template rule: **no issue is “ready” without acceptance criteria + validation commands.**

---

## 6) PR template

Add `.github/pull_request_template.md` with required sections:
- Linked issue(s) (`Closes #...`)
- What changed
- Why it changed
- Acceptance criteria mapping (issue AC -> proof)
- Test evidence (commands + outputs)
- Security/privacy impact
- Docs updated? (yes/no + path)
- Rollback notes

PR title convention:
- `feat(area): short summary (#issue)`
- `fix(area): short summary (#issue)`
- `docs(area): short summary (#issue)`

---

## 7) CODEOWNERS

Add `.github/CODEOWNERS` (or `/CODEOWNERS`) and assign reviewers by area, e.g.:
- `/backend/ @backend-owner`
- `/frontend/ @frontend-owner`
- `/.github/workflows/ @platform-owner`
- `/docs/ @docs-owner`

Guideline: at least one CODEOWNER review before merge for touched area.

---

## 8) Branch protection-lite (GitHub Free practical setup)

If branch protection/rulesets are available for this repository type:
- Protect `main`
- Require PR before merge
- Require at least 1 approval
- Require conversation resolution
- Require status checks: `CI / backend`, `CI / frontend`, `Security Scan / backend-audit`, `Security Scan / frontend-audit`
- Restrict force-push/deletions on `main`

If not available in your specific free-tier context:
- Enforce socially: no direct pushes to `main`
- Require maintainer merge only after CI green + review
- Use `state:do-not-merge` label to gate merges manually

---

## 9) Lightweight automation without paid features

Use GitHub Actions (free minutes permitting):
1. **Auto-label by file path** (`pull_request_target` + labeler config)
2. **Issue triage defaults** (set default labels/milestone on open)
3. **Stale management** (warn then close stale issues/PRs with exemptions)
4. **PR size labeler** (`size:xs/s/m/l/xl`) for review load balancing
5. **Release note draft job** from merged PR labels and milestone

None of the above require paid GitHub plans.

---

## 10) End-to-end workflow: idea -> issue -> PR -> merge -> release notes

1. **Idea capture**
   - Open issue via template.
   - Add type/area/priority labels.
   - Assign milestone.

2. **Triage (manager)**
   - Confirm scope, AC, validation commands.
   - Set Size + Owner + Target Date in Project.
   - Move to `Ready`.

3. **Execution**
   - Branch from `main` using naming convention below.
   - One issue per branch/PR.
   - Keep commits scoped; update docs/tests with code.

4. **PR open**
   - Link issue (`Closes #...`).
   - Fill PR template completely.
   - Ensure CI + security checks are green.

5. **Review**
   - CODEOWNER review required.
   - Resolve comments; avoid squash-amend cycles that hide review context unless needed.

6. **Merge**
   - Prefer squash merge with structured commit title.
   - Issue auto-closes; project item moves to Done.

7. **Release notes**
   - At milestone close, generate notes grouped by labels (`type:*`, `area:*`, `security`).
   - Tag release (`vX.Y.Z`) and publish.

---

## 11) Naming conventions

## Branch names
- `feat/<area>-<short-desc>-#<issue>`
- `fix/<area>-<short-desc>-#<issue>`
- `docs/<area>-<short-desc>-#<issue>`

Examples:
- `feat/meta-critic-default-view-#128`
- `fix/auth-settings-admin-gate-#141`

## Issue titles
- `[M1][meta-critic] Default to meta directives on document open`
- `[M3][security] Add request-id + latency metadata to all API responses`

## Milestone naming
- `M1 Meta-first UX + synthesis orchestration`
- `M2 Persona contract reliability`
- `M3 Platform hardening`
- `M4 Delivery throughput + API boundary`

## Release naming
- `v0.2.0-m1`
- `v0.3.0-m2`

---

## 12) Weekly operating cadence (lightweight)

- **Monday:** triage + reprioritize board, unblock `state:blocked`.
- **Daily async:** update issue status/estimates, no hidden work.
- **Friday:** merge window + milestone burndown + release note draft.

Cadence KPI targets:
- < 24h to initial triage for new P0/P1 issues
- < 3 days median cycle time for S/M issues
- 0 direct pushes to `main`

---

## 13) Minimal implementation checklist (recommended files to add)

- `.github/ISSUE_TEMPLATE/feature.yml`
- `.github/ISSUE_TEMPLATE/bug.yml`
- `.github/ISSUE_TEMPLATE/security.yml`
- `.github/ISSUE_TEMPLATE/spike.yml`
- `.github/ISSUE_TEMPLATE/ops.yml`
- `.github/pull_request_template.md`
- `.github/labeler.yml`
- `.github/workflows/labeler.yml`
- `.github/workflows/stale.yml`
- `.github/CODEOWNERS`

This checklist is intentionally compatible with GitHub Free and can be implemented incrementally in small PRs.
