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
