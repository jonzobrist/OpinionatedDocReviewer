# Beta Readiness

Last updated: 2026-02-11

## Current Status
- Backend API tests: `12 passed` (`uv run pytest`)
- Frontend tests: `9 passed` (`bunx vitest run`)
- Frontend build: passes (`bun run build`)

## UI Controls Audit
- `Library` (top nav): opens review ledger overlay. Verified by UI test.
- `System` (top nav): opens settings drawer and saves API base + tenant to local storage. Verified by UI test.
- `History` (top nav): toggles history drawer when a document is open. Code-audited; needs UI test.
- `Agents` (top nav): toggles agents drawer when a document is open. Code-audited; needs UI test.
- `+ Upload` and drag/drop: create doc/version and queue review automatically. Covered by flow test + manual validation.
- `Run Review` (doc view): queues manual review job. Code-audited; needs UI test.
- `Refresh` (comments panel): reloads comments for selected version/job. Code-audited; needs UI test.
- Library card actions `Open`, `Run Review`, `Re-run`, `Archive/Restore`, delete `×`: code-audited; backend endpoints tested.
- Library bulk actions `Archive Selected`, `Restore Selected`, `Re-run Selected`, `Delete Selected`: code-audited; backend endpoints tested.

## Beta Gaps (High Priority)
- Add UI smoke tests for in-document controls (`Run Review`, agent toggles, history drawer, refresh).
- Add UI smoke tests for library card actions and bulk actions with mocked API calls.
- Add one end-to-end happy path smoke test (upload -> auto-review queued -> comments shown).
- Add CI commands that run:
  - `cd backend && uv sync --extra test && uv run pytest`
  - `cd frontend && bunx vitest run && bun run build`

## Risk Notes
- `Run Review` and `Re-run` in library currently execute the same behavior intentionally; wording can be clarified for users.
- Frontend `test` script currently runs watch mode; use `bunx vitest run` for non-interactive CI.
