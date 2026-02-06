# OpinionatedDocReviewer - Engineering Playbook

## Purpose
Build a scalable, secure, and fast web application to review documents and multiple document versions using configurable GenAI personas. The UI should look like a professional, modern document review tool with clear persona-themed comments, toggles, and groupings.

This document is optimized for future contributors (including AI agents) to quickly understand the system, the standards, and the next steps.

## Product Goals
- Review AI-generated or human documents with opinionated, persona-based feedback.
- Manage personas and persona groups entirely via the web UI.
- Support multiple document versions and diffs.
- Enterprise-ready look and feel (boardroom-grade, clean, technical).
- High security and strong performance.
- All user actions go through backend APIs.
- Full test coverage (unit + integration) and CI enforcement.

## Default Technical Assumptions
- Multi-tenant SaaS.
- Auth: OIDC + OAuth + password/MFA.
- Frontend: React (Next.js recommended for SSR and app shell performance).
- Backend: Python (FastAPI), async where possible.
- DB: Postgres, Redis cache for speed, S3-compatible object storage for documents.
- API: REST for CRUD and core flows, WebSocket for live collaboration/updates.
- AI: pluggable provider abstraction (OpenAI/Anthropic/AWS Bedrock, etc).

## Architecture Overview
- Web UI (React/Next.js)
  - Document viewer with inline comment markers.
  - Persona toggles and persona group selectors.
  - Diff viewer for versions.
  - Admin screens for personas, groups, policies, auth, and system config.
- API Service (FastAPI)
  - Auth (OIDC/OAuth/password/MFA).
  - Document versioning and diff pipelines.
  - Persona management and review orchestration.
  - Multi-tenant authorization and audit logging.
  - Rate limiting, throttling, and content security.
- Async workers
  - Queue for AI review jobs and diff computation.
  - Streaming results back to UI.
- Storage
  - Postgres for metadata.
  - S3-compatible object store for documents.
  - Redis for cache and job status.

## Key Domains and Concepts
- Document: a logical artifact.
- Version: immutable snapshot with metadata and content.
- Comment: persona-authored feedback anchored to ranges.
- Persona: configurable system prompt, rules, tone, and focus areas.
- Persona Group: bundles of personas for specific content types.
- Review Job: orchestration of persona feedback on a version or diff.

## API Standards
- All UI interactions must go through the API.
- Every endpoint uses:
  - AuthZ and AuthN checks.
  - Throttling (per user, per tenant).
  - Input validation and size limits.
  - Audit logging for mutating actions.
- All API responses include request IDs and latency metadata.
- Prefer REST for CRUD, WebSocket/Server-Sent Events for streaming updates.

## Security Standards
- Strict tenant isolation.
- Secrets stored in a secret manager.
- Encrypted at rest for documents.
- TLS everywhere for in-transit data.
- Minimum-privilege roles.
- Full audit trail for content changes and reviews.

## Testing Standards (Required)
- Every module must have unit tests.
- All API endpoints must have integration tests.
- Tests must be deterministic.
- PRs must include tests for new features.
- CI gates:
  - Unit tests.
  - Integration tests.
  - Linting and type checks.
  - Security checks (SAST + dependency scanning).

## Milestones (High Level)
1. Core foundations: auth, tenant model, document storage, persona CRUD.
2. Review pipeline: async AI review orchestration, comment schema.
3. UI v1: document viewer, persona toggle UI, comment rendering.
4. Versioning + diff: multi-version support with inline diff viewer.
5. Enterprise features: audit logs, rate limiting, admin configs.
6. Performance and scale: caching, streaming, indexing, load tests.

## First Tasks (If Starting Fresh)
- Define data model and schemas.
- Implement document CRUD and versioning endpoints.
- Implement persona CRUD and grouping.
- Implement review job orchestration (queue + worker).
- Implement comment schema and anchor model.
- Build UI document viewer and comment rendering.
- Build persona admin UI with toggle/group management.
- Add integration tests for key flows.

## How to Work in This Repo
- Always read AGENTS.md before starting.
- Add or update docs when changing architecture or workflows.
- Every change must include tests.
- Keep code modular and well-typed.
- Prefer small, reviewable PRs.

