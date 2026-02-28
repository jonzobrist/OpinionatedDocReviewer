# Finish Line TODO

## Core Workflow
- [x] Minimal landing with drag/drop upload
- [x] Auto-create doc + version + queue review
- [x] Live feed + inline highlights
- [x] Agent list hidden by default
- [x] Git-backed document history
- [x] Review outputs persisted per version (DB + git)

## Reliability + Clarity
- [x] System status endpoint (redis/openai)
- [x] UI banner for missing Redis/OpenAI key
- [x] Redis helper script for start/stop/status
- [x] CORS strategy documented + configurable settings

## Polished UI
- [x] Redesign UI per new aesthetic
- [x] Live comment arrival animation
- [x] Library redesigned with review status + explicit run action
- [x] Highlight-to-comment connector lines with curved paths
- [x] Feed ordering aligned to document anchor position
- [x] Reviewer toggles hide/show their highlights and comments

## Testing
- [x] Backend status endpoint test
- [x] Frontend status type test
- [x] End-to-end review job test with Redis + mocked OpenAI
- [x] UI helper tests for themes + types
- [x] UI integration-style test for upload -> queue flow (mock API)
- [x] Library API test (latest version + needs review)

## Remaining Work
- [x] Ensure worker auto-retries + backoff
- [x] Add agent theme customization UI (advanced drawer)

## Core Feature Hardening
- [x] Immediate document display on upload while review runs in background
- [x] Parallel persona review execution for faster live updates
- [x] Explicit-only re-review flow (normal open/view does not re-run)
- [x] Persist and reload review results by version
- [x] Library actions: archive, restore, delete, review, re-review
- [x] Library bulk actions: archive, restore, delete, re-review

## Agent Functionality Roadmap
### Phase 1: Data Model + API
- [x] Extend persona schema with richer config:
- [x] Add `output_requirements` (markdown template, max bullets, citation/quote rules, severity tags).
- [x] Add `reference_notes` (long-form context the agent should always consider).
- [x] Add `examples` (few-shot example inputs/outputs to shape style).
- [x] Add `is_default` and `is_system_locked` for persistent built-in agents.
- [x] Add `sort_order` and `color_theme` so agent display is deterministic and customizable.
- [x] Add migration path for existing DBs and backfill defaults.
- [x] Add API validation for required/optional fields and safe limits.
- [x] Add API route to reset built-in agents to baseline defaults without deleting user agents.

### Phase 2: Review Engine Integration
- [x] Update prompt builder to include new persona fields consistently.
- [x] Enforce `output_requirements` in prompt and parser fallback behavior.
- [x] Persist per-comment metadata indicating which output rule was applied/violated.
- [x] Add safety guards for oversized reference notes/examples.

### Phase 3: Full CRUD UI for Agents
- [x] Build `/agents` as full management page (not just drawer):
- [x] Agent list, search, sort, active toggle.
- [x] Create form with advanced sections:
- [x] Core identity: name, description, tone.
- [x] Prompting: system prompt, focus areas, reference notes.
- [x] Output contract: required format, bullet count, mandatory quote/citation options.
- [x] Display settings: color theme, icon/label.
- [x] Edit + duplicate + delete actions.
- [x] Guardrails for system default agents (lock/delete behavior, reset option).

### Phase 4: Defaults + Persistence Behavior
- [x] Ensure default agents are always present per tenant.
- [x] Prevent accidental deletion of default agents unless explicitly converted to user agent.
- [x] Add "Restore defaults" action with preview of what will change.

### Phase 5: Testing + QA
- [x] Backend tests for new persona schema and migrations.
- [x] Backend tests for prompt assembly with new fields.
- [x] Frontend tests for full CRUD flows on `/agents`.
- [x] Regression tests ensuring default agents persist across restarts.
- [x] E2E smoke test: create custom agent -> run review -> comments reflect new output requirements.
