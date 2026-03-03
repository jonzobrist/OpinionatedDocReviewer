# GitHub Project Bootstrap Checklist (GitHub Free)

Last updated: 2026-03-01

Applies to repository root: `/home/zob/src/OpinionatedDocReviewer`

Primary references:
- `/home/zob/src/OpinionatedDocReviewer/docs/process/github-free-workflow.md`
- `/home/zob/src/OpinionatedDocReviewer/docs/plans/m1-meta-first-issue-backlog.md`
- `/home/zob/src/OpinionatedDocReviewer/.github/workflows/ci.yml`
- `/home/zob/src/OpinionatedDocReviewer/.github/workflows/security-scan.yml`

---

## Goal

Get a GitHub Free-compatible operating system live for M1 in one session, with minimal ambiguity for assignment and tracking.

---

## Step-by-step setup checklist

## 0) Preconditions (5 minutes)

- [ ] You have maintainer/admin rights on the GitHub repo.
- [ ] Default branch is `main`.
- [ ] GitHub Actions are enabled.
- [ ] Optional: `gh` CLI is installed and authenticated (`gh auth status`).

If `gh` is available, use:
- `/home/zob/src/OpinionatedDocReviewer/scripts/github/bootstrap-labels-milestones.sh`

---

## 1) Labels (10 minutes)

- [ ] Create/update the standard label taxonomy (type, area, priority, state, risk, impact, size).
- [ ] Confirm at minimum these are present:
  - Types: `type:feature`, `type:bug`, `type:refactor`, `type:docs`, `type:test`, `type:security`, `type:ops`, `type:spike`
  - Areas: `area:backend`, `area:frontend`, `area:review-engine`, `area:meta-critic`, `area:auth`, `area:security`, `area:infra`, `area:ci`, `area:docs`
  - Priorities: `prio:p0`, `prio:p1`, `prio:p2`, `prio:p3`
- [ ] Add status labels: `state:ready`, `state:in-progress`, `state:needs-review`, `state:blocked`, `state:needs-info`, `state:do-not-merge`

**CLI (dry-run):**
```bash
cd /home/zob/src/OpinionatedDocReviewer && /home/zob/src/OpinionatedDocReviewer/scripts/github/bootstrap-labels-milestones.sh
```

**CLI (apply):**
```bash
cd /home/zob/src/OpinionatedDocReviewer && /home/zob/src/OpinionatedDocReviewer/scripts/github/bootstrap-labels-milestones.sh --apply
```

---

## 2) Milestones (5 minutes)

- [ ] Create milestones:
  - `M1 Meta-first UX + synthesis orchestration`
  - `M2 Persona contract reliability`
  - `M3 Platform hardening`
  - `M4 Delivery throughput + API-boundary maturity`
- [ ] Set due dates and milestone descriptions (objective + exit criteria + validation commands).
- [ ] Confirm all M1 kickoff issues map to M1 milestone.

Suggested due dates for initial setup:
- M1: 2026-03-27
- M2: 2026-04-24
- M3: 2026-05-22
- M4: 2026-06-19

---

## 3) Project board (GitHub Projects v2) (15 minutes)

- [ ] Create project: **`ODR Delivery Board`**.
- [ ] Add custom fields:
  - `Status` (Todo, Ready, In Progress, In Review, Blocked, Done)
  - `Priority` (P0, P1, P2, P3)
  - `Type` (Feature, Bug, Refactor, Docs, Test, Security, Ops, Spike)
  - `Area` (Backend, Frontend, Meta, Auth, Security, CI, Docs)
  - `Milestone` (M1, M2, M3, M4)
  - `Size` (XS, S, M, L, XL)
  - `Owner` (assignee)
  - `Target Date` (date)
  - `Risk` (Low, Medium, High)
- [ ] Create views:
  1. Backlog by Priority
  2. Current Milestone Kanban
  3. By Area
  4. Review Queue
  5. Blocked
  6. Done This Week
- [ ] Set `Current Milestone Kanban` as default view.

---

## 4) Required checks and branch protection (10 minutes)

### Required checks names (configure exactly)

From `/home/zob/src/OpinionatedDocReviewer/.github/workflows/ci.yml`:
- `CI / backend`
- `CI / frontend`

From `/home/zob/src/OpinionatedDocReviewer/.github/workflows/security-scan.yml`:
- `Security Scan / dependency-review` *(PR-triggered job)*
- `Security Scan / backend-audit`
- `Security Scan / frontend-audit`

### Branch protection setup

If branch protection/rulesets are available:
- [ ] Protect `main`
- [ ] Require pull request before merge
- [ ] Require at least 1 approval
- [ ] Require conversation resolution
- [ ] Require the checks listed above
- [ ] Disallow force-push and branch deletion on `main`

### Branch protection fallback (if unavailable in your GitHub Free context)

- [ ] Enforce “no direct pushes to `main`” as team policy.
- [ ] Maintainer-only merge after review + green CI.
- [ ] Use `state:do-not-merge` to manually block unsafe PRs.
- [ ] Require PR template completion and linked issue for every PR.

---

## 5) Seed M1 work items into project (10 minutes)

- [ ] Create issues from `/home/zob/src/OpinionatedDocReviewer/docs/plans/m1-meta-first-issue-backlog.md` (M1-01 … M1-12).
- [ ] Apply required labels (one type + one priority + 1-2 areas).
- [ ] Assign owner role and target date.
- [ ] Add every issue to `ODR Delivery Board`.
- [ ] Set initial status:
  - `Ready`: scoped + AC + validation commands complete.
  - `Blocked`: missing dependency or decision.

---

## 6) Definition of Ready / Done enforcement (5 minutes)

- [ ] Definition of Ready for issue:
  - Scope + non-goals documented.
  - Acceptance criteria checklist included.
  - Validation commands included.
  - Milestone + labels applied.
- [ ] Definition of Done for PR:
  - Linked issue closes on merge.
  - Tests pass and required checks are green.
  - Docs updated where behavior changed.
  - Risk/rollback note added for user-visible changes.

---

## Day-1 setup in <60 minutes

| Timebox | Task |
|---|---|
| 0-5 min | Verify permissions, Actions enabled, default branch `main`. |
| 5-15 min | Run label/milestone bootstrap script (or manual setup). |
| 15-30 min | Create `ODR Delivery Board`, fields, and six views. |
| 30-40 min | Configure branch protections and required checks (or fallback policy). |
| 40-55 min | Create/label/assign M1 kickoff issues from backlog doc. |
| 55-60 min | Quick triage pass: set `Ready` vs `Blocked`, announce kickoff. |

Fast-path command sequence:
```bash
cd /home/zob/src/OpinionatedDocReviewer
/home/zob/src/OpinionatedDocReviewer/scripts/github/bootstrap-labels-milestones.sh
/home/zob/src/OpinionatedDocReviewer/scripts/github/bootstrap-labels-milestones.sh --apply
```

---

## First week operating cadence

### Day 1 (Kickoff)
- Finalize issue ownership by role and dependency sequencing.
- Move unblocked M1 issues to `In Progress`.

### Day 2-4 (Execution)
- Daily async updates in issues (status, blockers, next step).
- Keep one primary owner per issue; pair only when dependencies require.
- Enforce no hidden work: everything tracked as issue/PR.

### Day 3 (Mid-week risk review)
- Review `Blocked` and `Review Queue` views.
- Escalate scope cuts if M1 critical path slips.
- Reconfirm branch protection and check stability.

### Day 5 (Weekly close)
- Merge window for ready PRs.
- Reconcile milestone burndown against target date.
- Draft incremental release notes grouped by `type:*` and `area:*` labels.

Cadence KPIs (week 1 target):
- New P0/P1 issue triaged in <24 hours.
- Median cycle time for S/M issues <3 days.
- 0 direct pushes to `main`.

---

## Optional but recommended immediate follow-ups

- Add issue templates under `/home/zob/src/OpinionatedDocReviewer/.github/ISSUE_TEMPLATE/`.
- Add PR template at `/home/zob/src/OpinionatedDocReviewer/.github/pull_request_template.md`.
- Add CODEOWNERS at `/home/zob/src/OpinionatedDocReviewer/.github/CODEOWNERS`.
- Add auto-label/stale workflows once M1 issue flow is stable.
