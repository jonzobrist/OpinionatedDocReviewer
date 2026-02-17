# Security Audit — OpinionatedDocReviewer

**Auditor:** RueClaw (automated)
**Date:** 2026-02-17
**Scope:** Full repository review (backend, frontend, scripts, configuration)

---

## Summary

The application is an AI-powered document review platform with a FastAPI backend, Next.js frontend, Redis job queue, and SQLite database. It supports multi-tenancy via headers and has basic RBAC. Overall the codebase is clean and well-structured, but has several security concerns — primarily around authentication/authorization design and the settings endpoint.

| Severity | Count |
|----------|-------|
| 🔴 Critical | 1 |
| 🟠 High | 3 |
| 🟡 Medium | 4 |
| 🔵 Low | 4 |
| ℹ️ Info | 2 |

---

## Findings

### 🔴 CRITICAL

#### C1: Header-Based Authentication Is Trivially Spoofable

**File:** `backend/app/api/deps.py`

Authentication relies entirely on client-supplied `X-Tenant-Id`, `X-User-Email`, and `X-User-Id` headers. Any caller can impersonate any user or tenant by setting these headers. There is no token validation, session management, or cryptographic authentication.

```python
def get_request_user(
    x_user_email: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> models.User:
    # Falls back to admin if no headers provided
    if not x_user_email and not x_user_id:
        query = query.filter(models.User.role == "admin")
```

**Impact:** Complete bypass of all authorization. Any unauthenticated user can access admin endpoints, read/modify any tenant's data, and manage all documents.

**Recommendation:**
- Implement proper authentication (JWT, OAuth2, or session-based)
- Never trust client-supplied identity headers without verification
- If this is intentionally behind a reverse proxy that sets these headers, document that requirement and validate the request origin

---

### 🟠 HIGH

#### H1: Settings Endpoint Writes Secrets to Plaintext Config File — No Auth Required

**Files:** `backend/app/api/settings.py`, `backend/app/core/config.py`

The `PUT /api/settings` endpoint accepts API keys (OpenAI, AWS credentials) and writes them to `config.toml` in plaintext. This endpoint only requires `X-Tenant-Id` — no admin check.

```python
@router.put("", response_model=SystemConfigRead)
def update_settings(payload: SystemConfigUpdate, _: str = Depends(get_tenant_id)):
    # No admin check — any user with a tenant header can update settings
    if payload.openai_api_key is not None:
        settings.OPENAI_API_KEY = payload.openai_api_key.strip() or None
        updates["OPENAI_API_KEY"] = settings.OPENAI_API_KEY or ""
```

**Impact:** Any caller can overwrite API keys, redirect LLM calls to a malicious endpoint, or exfiltrate existing keys by changing the provider configuration.

**Recommendation:**
- Gate settings endpoints behind `require_admin_user`
- Never persist secrets in plaintext config files; use environment variables or a secrets manager
- Don't echo secret values back in responses (currently masked with `_set` booleans, which is good)

#### H2: `GET /api/settings` Exposes Internal Configuration

**File:** `backend/app/api/settings.py`

The settings GET endpoint exposes Redis URLs, CORS configuration, file paths, and internal service details to any caller with a tenant header.

**Impact:** Information disclosure aids further attacks — Redis URL enables direct access attempts, file paths reveal server structure.

**Recommendation:** Restrict to admin users; redact sensitive fields from response.

#### H3: Tenant Isolation Depends Entirely on Client-Supplied Header

**File:** `backend/app/api/deps.py`

All data is scoped by `X-Tenant-Id` header. Since there's no authentication, any caller can access any tenant's data by changing this header.

**Impact:** Complete cross-tenant data access.

**Recommendation:** Derive tenant from authenticated session, not from a client-supplied header.

---

### 🟡 MEDIUM

#### M1: `subprocess.run` in Git Operations — Low Risk but Worth Noting

**File:** `backend/app/reviews/git_repo.py`

Git operations use `subprocess.run` with list-based arguments (not shell=True), which is good. However, `tenant_id` and `document_id` flow into file paths without sanitization beyond type checking.

```python
def ensure_repo(tenant_id: str, document_id: int) -> Path:
    repo_path = root / tenant_id / f"doc-{document_id}"
    repo_path.mkdir(parents=True, exist_ok=True)
```

**Impact:** If `tenant_id` contains path traversal characters (e.g., `../../etc`), it could write outside the intended directory.

**Recommendation:**
- Validate `tenant_id` against a strict pattern (alphanumeric + hyphens)
- Use `Path.resolve()` and verify the result is within `DOC_REPO_ROOT`

#### M2: No Rate Limiting on API Endpoints

**Impact:** LLM review endpoints can be abused to rack up API costs. No rate limiting exists on any endpoint.

**Recommendation:** Add rate limiting middleware (e.g., `slowapi` for FastAPI).

#### M3: CORS Configured with Wildcard Methods and Headers

**File:** `backend/app/core/config.py`

Default CORS allows `*` for methods and headers. While origins are restricted, this is more permissive than necessary.

**Recommendation:** Restrict to specific methods (`GET, POST, PUT, PATCH, DELETE, OPTIONS`) and headers actually used.

#### M4: SQLite Database File in Working Directory

**File:** `backend/app/core/config.py`

Default `DATABASE_URL = "sqlite:///./app.db"` places the database in the working directory. If the web server serves static files from the same tree, the database could be exposed.

**Recommendation:** Store the database outside the web-accessible directory; ensure `.db` files are never served.

---

### 🔵 LOW

#### L1: No CSRF Protection

The API uses custom headers (`X-Tenant-Id`) which provides implicit CSRF protection for JSON requests (browsers won't send custom headers cross-origin without CORS preflight). However, there's no explicit CSRF token mechanism.

**Recommendation:** Acceptable for API-only backends with proper CORS. Document this design decision.

#### L2: Debug Mode in Production

**File:** `backend/app/main.py`

`uvicorn.run` with `reload=True` is set in the `run()` function. The startup scripts also don't pass `--reload`, which is correct, but the `run()` function default could be accidentally used.

**Recommendation:** Remove `reload=True` from the default run function; use it only in dev scripts.

#### L3: Error Messages May Leak Internal Details

Exception messages from LLM providers are passed directly to clients in some error paths (e.g., meta_reviews endpoint: `f"Meta synthesis failed: {exc}"`).

**Recommendation:** Log detailed errors server-side; return generic messages to clients.

#### L4: No Input Size Limits on Document Content

Document content is accepted without explicit size limits beyond `OPENAI_MAX_INPUT_CHARS` (which only trims for LLM calls, not storage).

**Recommendation:** Add request body size limits in the web server or middleware.

---

### ℹ️ INFORMATIONAL

#### I1: No Secrets Found in Git History

Searched git history for passwords, API keys, and tokens. Only placeholder values (`your-key-here`) found in example files. `.env` and `config.toml` are properly gitignored. ✅

#### I2: Dependencies Are Reasonably Current

- FastAPI, Pydantic, SQLAlchemy, OpenAI, and Next.js versions are recent
- No known critical CVEs in the pinned dependency versions at time of audit
- `jsdom 24.0.0` (dev dependency) should be monitored for updates
- No `npm audit` or `pip audit` run (no lock files for pip; bun.lock exists for frontend)

**Recommendation:** Add `npm audit` / `pip audit` to CI pipeline.

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| 1 | Implement real authentication (JWT/OAuth2) — this is the single biggest issue |
| 2 | Gate `/api/settings` behind admin authentication |
| 3 | Validate `tenant_id` format (strict alphanumeric pattern) |
| 4 | Add rate limiting to LLM-calling endpoints |
| 5 | Add dependency vulnerability scanning to CI |
| 6 | Restrict CORS methods/headers to actual needs |
| 7 | Add request body size limits |
| 8 | Sanitize error messages in API responses |

---

## Scope Notes

- **Docker/deployment:** No Dockerfile found in repo; deployment uses shell scripts with proper `set -euo pipefail`
- **License:** No LICENSE file present — unclear licensing status; recommend adding one
- **Supply chain:** Dependencies are from well-known packages; no suspicious or typosquatted packages detected
- **XSS:** Frontend uses React (auto-escapes by default) and `react-markdown` with `remark-gfm`; document content rendered as markdown is a potential vector but React's JSX escaping mitigates most risks
- **SSRF:** The `next.config.js` rewrites proxy to localhost:8006 only; no user-controlled URL fetching detected
