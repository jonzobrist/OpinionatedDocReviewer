# Reliable pilot execution plan

Date: 2026-11-07
Status: active; implementation in small, tested commits.

## Goal

Deliver a trustworthy document-review pilot: authorized users can upload, review,
understand what was reviewed, act on grounded feedback, and reopen a stable result.
Existing assessment/roadmap drafts in this checkout are preserved separately; this
file records the implementation sequence authorized in this chat.

## Verified baseline

At local commit eb6ca46: 142 backend tests and 47 frontend tests passed; the
network-enabled frontend production build passed. Live-provider, real Redis worker,
and browser acceptance checks were not performed. Remote issue status was not
verified. Passing tests establish a regression baseline, not review usefulness.

Implemented: document versions/history, parallel anchored persona reviews, agent
editing and portability, meta-first verdict/attention points/source drill-down,
bounded polling, and authentication/document-policy foundations. SQLite/local Git
and polling are current architecture; Postgres/S3 and streaming are future options.

## Ordered work

1. **Persona API protections (first slice).** Restrict persona/group mutations,
   imports, and resets to existing admin roles. Protect built-in persona identity
   flags and deletion on the server, retain editable prompts and reset behavior,
   and reject references to another tenant's group. Verify denied requests do not
   mutate data, allowed administration still works, and reads remain available.
2. **Document access for meta reviews.** Reuse existing document-permission checks
   for create/ensure/latest, including metadata-only responses. Test same-tenant
   denial, explicit-deny policies, allowed users, and cross-tenant behavior.
3. **Honest review outcomes and stable verdicts.** Define reviewed scope and
   partial/failed reviewer semantics; never label an unreviewed tail clean. Persist
   verdict/provenance per synthesis run; GET/reopen must make zero provider calls.
4. **Deployment and reliability.** Reconcile API routing and queue-default docs;
   document authenticated deployment; align worker/retry deadlines and idempotency.
   Prove frozen installation, tests/build, backup/restore, and a disposable browser
   workflow through upload, result, source click, reopen, and a new version.
5. **Documentation reconciliation.** Update README, backend README, TODO, beta
   readiness, and security remediation status against code and recorded checks.
   Preserve dated audits/release snapshots as historical evidence. Consolidate
   remaining work and remove broken machine-specific/missing-file references.
6. **Usefulness evaluation.** Prepare 6–10 approved synthetic/non-sensitive fixtures,
   including clean, flawed, repetitive, contradictory, and over-limit documents.
   Compare multiple personas plus synthesis with one constrained reviewer. Record
   useful/unsupported/missed/redundant findings, cost, latency, and repeatability.
   Paid live runs require approved data/provider budget; no deployment or outreach
   is implied by this plan.

## Decision gates

- Trust: unauthorized operations fail; review scope/failure is explicit; reads are
  stable and inference-free.
- Reliability: one reproducible authenticated workflow survives ordinary failures.
- Usefulness: author judgment demonstrates better findings or less effort than a
  single-reviewer baseline. Otherwise simplify before expanding.
- Expansion: choose version comparison for recurring authors, platform hardening
  for teams, or CLI integration for automation from observed audience needs.

Defer marketplaces, mobile clients, extra orchestration, storage migration, and
broader integrations until the pilot supplies evidence for them.

## Progress

- [x] Review implementation/docs and run baseline checks.
- [x] Record execution plan.
- [x] Persona API protections and regressions.
- [x] Meta-review document authorization.
- [ ] Scope/outcome contract and persisted verdicts.
- [ ] Deployment/reliability evidence.
- [ ] Documentation reconciliation.
- [ ] Usefulness evaluation and next investment decision.

## GitHub reconciliation — 2026-11-07

Live public GitHub issues/PRs were verified after the initial baseline. The GitHub
connector supplied open issues, PRs, and remote plan files; public REST supplied
milestones, PR check runs/mergeability, and the latest issue comments.

### Product backlog and plans

- [#49 — reruns must use currently enabled reviewers](https://github.com/jonzobrist/OpinionatedDocReviewer/issues/49)
  is the only open non-PR issue. It is labeled P0/in-progress in M3, with no
  assignee. Verify the current behavior against an enable-new-reviewer → rerun
  regression and clarify refresh-versus-rerun semantics before closing it. Include
  this in the pilot reliability work; do not create a duplicate issue. Its 637
  comments and recent bot-only watchdog updates are not evidence of implementation
  progress. Tune watchdog noise as a separate process improvement.
- [M1](https://github.com/jonzobrist/OpinionatedDocReviewer/milestone/1) is closed
  with 12 closed items; [M2](https://github.com/jonzobrist/OpinionatedDocReviewer/milestone/2)
  is closed with 11. Historical local M1/M2 docs must reflect closeout.
- [M3](https://github.com/jonzobrist/OpinionatedDocReviewer/milestone/3) remains
  open, with #49 remaining and three items closed; its May 22 target is historical.
- [M4](https://github.com/jonzobrist/OpinionatedDocReviewer/milestone/4) is still
  open although all four items are closed. Closure is not proof of delivery:
  [Deslop #42](https://github.com/jonzobrist/OpinionatedDocReviewer/issues/42),
  [summary endpoint #56](https://github.com/jonzobrist/OpinionatedDocReviewer/issues/56),
  and [streaming #57](https://github.com/jonzobrist/OpinionatedDocReviewer/issues/57)
  were explicitly closed as **not planned** on May 25. Do not revive these from
  old theory text. The existing meta-review API remains implemented; #56 proposed
  a distinct endpoint. The referenced shared-vault TUI plan was not accessible in
  this review and is not treated as an active commitment.
- Remote `main` currently has only `m2-execution-status.md` under `docs/plans`.
  The local dated assessment/roadmap drafts were not already published there.

### Open dependency PRs

| PR | Scope | Observed checks/mergeability | Next action |
|---|---|---|---|
| [#164](https://github.com/jonzobrist/OpinionatedDocReviewer/pull/164) | anyio 4.12.1 → 4.14.2 | Mergeable; backend/frontend pass, frontend audit fails | Diagnose audit failure and validate on current base |
| [#163](https://github.com/jonzobrist/OpinionatedDocReviewer/pull/163) | sharp + Next 15.5.25 | Conflicts; frontend and frontend audit fail | Reconcile with #158; prefer a tested maintained patch path if sufficient |
| [#161](https://github.com/jonzobrist/OpinionatedDocReviewer/pull/161) | nanoid 3.3.11 → 3.3.18 | Conflicts; backend/frontend pass, frontend audit fails | Rebase/consolidate and inspect current dependency tree |
| [#158](https://github.com/jonzobrist/OpinionatedDocReviewer/pull/158) | postcss + Next 16.3.0 | Conflicts; no check runs returned for current head | Treat as a major framework upgrade requiring separate validation |

Add dependency remediation to the release gate, alongside API protections. These
are snapshots, not proof that all failures originate in the changed dependency.
Do not blindly merge overlapping Next updates. GitHub Project boards were not
inspected; milestone/issue descriptions and remote repo plans are the verified
planning sources. No issues, comments, labels, milestones, or existing PRs were
modified by this reconciliation.

## First implementation receipt

Implemented persona/group management-role checks, server-managed built-in flags
and deletion protection, tenant-scoped group assignment validation, and document
ACL enforcement on all three meta-review routes. Full and metadata-only reads
require viewer permission; create/ensure require editor permission. Explicit-deny
policy, missing/cross-tenant versions, unauthorized synthesis, allowed roles, and
mutation atomicity have regression coverage.

Validation: `uv run --directory backend --extra test pytest` — **156 passed**,
five existing short-JWT-test-key warnings. Frontend source is unchanged; its 47-test
and production-build baseline comes from the preceding review. No production
service, provider, or external document was used. Remaining pilot work starts with
scope/failure semantics and stable persisted verdicts; #49 and dependency PR
reconciliation remain open. API write access is intentionally narrower: existing
non-admin persona-management clients now receive 403; built-in flag changes return
422 and protected deletion returns 409.
