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
- [ ] Persona API protections and regressions.
- [ ] Meta-review document authorization.
- [ ] Scope/outcome contract and persisted verdicts.
- [ ] Deployment/reliability evidence.
- [ ] Documentation reconciliation.
- [ ] Usefulness evaluation and next investment decision.
