# Product Information

## CORS Strategy (Safe Defaults + Configurable)

We treat CORS as an expected, configurable part of the product surface. The goal is to keep the default experience frictionless for local development, while keeping production safe by default.

### Principles
- Prefer same-origin in production (serve UI and API under one origin), and only enable cross-origin access when needed.
- Use an explicit allowlist of trusted origins for private APIs. Avoid wildcard origins for authenticated endpoints.
- Never combine `Access-Control-Allow-Credentials: true` with a wildcard origin. The origin must be explicit when credentials are allowed. citeturn0search7turn0search6
- Avoid reflecting arbitrary `Origin` headers. That effectively trusts untrusted origins and can enable data exposure. citeturn0search0turn0search4
- Expect preflight requests when custom headers or non-simple methods are used, and ensure the server responds correctly. citeturn0search1

### Recommended Configuration
Default (local dev):
- Allow `http://localhost:3000` and `http://127.0.0.1:3000`.
- `allow_credentials` defaults to `false`.
- `allow_methods` and `allow_headers` can be `*` for local dev convenience.

Production:
- Use a strict allowlist of UI origins (no wildcards).
- If credentials are needed (cookies or auth headers), keep `allow_credentials=true` and list each allowed origin explicitly. citeturn0search7turn0search6
- If you must allow public read-only access, use `Access-Control-Allow-Origin: *` and keep `allow_credentials=false`. citeturn0search6

### Config Surface (Backend)
All CORS settings are configurable via `.env` or `config.toml`:
- `CORS_ALLOW_ORIGINS`
- `CORS_ALLOW_ORIGIN_REGEX`
- `CORS_ALLOW_CREDENTIALS`
- `CORS_ALLOW_METHODS`
- `CORS_ALLOW_HEADERS`
- `CORS_MAX_AGE`

These settings map directly to FastAPI CORS middleware options. citeturn0search7

### Operational Checklist
- Confirm the UI origin matches a configured allowed origin.
- Verify preflight responses (`OPTIONS`) include allowed methods/headers and cache time.
- Do not rely on CORS for authentication. Always enforce auth on API routes. citeturn0search4
