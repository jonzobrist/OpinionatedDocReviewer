# Backend API

## Runtime and dependency installation

Use Python 3.11 or newer and install the committed dependency graph with uv:

```bash
uv sync --locked
```

The security baseline requires FastAPI 0.133+ (Starlette 1.x support),
Starlette 1.3.1+, AnyIO 4.14.2+, Pydantic Settings 2.14.2+,
PyJWT 2.15.1+, cryptography 50+, and urllib3 2.8+.
`uv.lock` records the exact tested releases; retain `--locked` in CI and deployments.
These minimums are also declared in `pyproject.toml` so an unlocked installation
cannot silently resolve the vulnerable versions this update replaces.

Platform changes in [cryptography 47–50](https://cryptography.io/en/latest/changelog/):
- Intel (`x86_64`) macOS and 32-bit Windows are no longer supported upstream.
  Use a supported Linux deployment, Apple Silicon macOS, or 64-bit Windows.
- Source builds require OpenSSL 3.0+ and Rust 1.83+; published wheels bundle OpenSSL.
  Prefer wheels on supported platforms.
- Python 3.11 remains supported. The dependency updates do not raise this project's
  Python minimum.

OIDC deployments must point `OIDC_JWKS_URL` directly at the final HTTP(S) JWKS
endpoint: PyJWT rejects redirects and other URI schemes. Publish rotated keys
before issuing tokens that use them; unknown key IDs are subject to PyJWT's
default 30-second refresh cooldown. Local HS256 authentication should use a
random `LOCAL_AUTH_JWT_SECRET` with at least 32 bytes.

## Run (local)
```bash
uv run --locked python -m app.main
```

## Worker (reviews)
The API runs reviews inline by default for reliability (`REVIEW_INLINE=true`).
Workers are optional for scale; enable `REVIEW_INLINE=false` to use the queue.

Requires Redis (default `redis://localhost:6379/0`) and an LLM provider configuration.

```bash
uv run --locked python -m app.worker
```

## API Notes
- Auth is configurable:
  - `AUTH_MODE=oidc`: requires `Authorization: Bearer <token>`
  - `AUTH_MODE=header`: accepts `X-Tenant-Id` / `X-User-Email` headers
- Port is configurable via `PORT` (default `8006`).
- Configure provider via `LLM_PROVIDER=openai|bedrock`.
- OpenAI: set `OPENAI_API_KEY`.
- Bedrock: set `BEDROCK_MODEL_ID`, `BEDROCK_REGION`, and AWS credentials (env/IAM role or Bedrock-specific keys).
- Review jobs are enqueued to Redis and processed by the worker.
- Document versions are committed to a per-document git repository under `.run/doc-repos` (configurable via `DOC_REPO_ROOT`).

## Provider Configuration Details

You can configure provider values in either:

- `backend/.env`
- `backend/config.toml`
- UI `System` panel (`http://localhost:3000`) for runtime config updates

### OpenAI

Required:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Optional:

```bash
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=700
OPENAI_TEMPERATURE=0.2
OPENAI_TIMEOUT_SECONDS=30
```

References:

- [OpenAI API keys](https://platform.openai.com/api-keys)
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [OpenAI models](https://platform.openai.com/docs/models)

### AWS Bedrock

Required:

```bash
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
BEDROCK_REGION=us-east-1
```

Credentials:

- Preferred: standard AWS credential resolution (IAM role, profile, SSO, etc.)
- Optional explicit settings:

```bash
BEDROCK_AWS_ACCESS_KEY_ID=...
BEDROCK_AWS_SECRET_ACCESS_KEY=...
BEDROCK_AWS_SESSION_TOKEN=... # optional
```

References:

- [Amazon Bedrock docs](https://docs.aws.amazon.com/bedrock/)
- [Supported Bedrock model IDs](https://docs.aws.amazon.com/bedrock/latest/userguide/foundation-models-reference.html)
- [Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
- [Boto3 credential configuration](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)

## Tests
```bash
uv sync --locked --extra test
uv run --locked pytest
```

The auth regressions exercise real HS256/RS256 signatures, JWKS parsing and cache
behavior, invalid claims, and preservation of caller-supplied JWT options.
The Bedrock smoke test uses the real Boto3/Botocore/urllib3 HTTP stack with fake
credentials and a loopback endpoint; it does not call AWS.

Audit the hashed, locked runtime graph (the same inventory deployed by uv):

```bash
uv export --locked --no-dev --no-emit-project --format requirements-txt --output-file /tmp/backend-requirements.txt
uv tool run pip-audit --strict --require-hashes --disable-pip -r /tmp/backend-requirements.txt
```

## Reverse Proxy Deployment

For deployments behind a reverse proxy (TLS at proxy, app local HTTP):

```env
ALLOWED_HOSTS=odr.zlyxy.me
TRUST_PROXY_HEADERS=true
PROXY_TRUSTED_IPS=*
```

Auth options:

```env
# Option A: simple non-IdP deployment
AUTH_MODE=header

# Option B: enterprise SSO/JWT
# AUTH_MODE=oidc
# OIDC_ISSUER_URL=...
# OIDC_AUDIENCE=...
# OIDC_JWKS_URL=...
```

If `AUTH_MODE=oidc` and no token is sent, API replies with:
`{"detail":"Authorization bearer token is required"}`.

## Debian 12/13 systemd Deployment

Use the bundled setup script to install persistent backend, worker, and frontend services.

1. Install base packages:

```bash
sudo apt-get update
sudo apt-get install -y git curl build-essential python3 python3-venv redis-server
```

2. Install Bun and uv (once):

```bash
curl -fsSL https://bun.sh/install | bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Clone app and prepare deps:

```bash
sudo mkdir -p /opt/OpinionatedDocReviewer
sudo chown -R "$USER":"$USER" /opt/OpinionatedDocReviewer
git clone https://github.com/jonzobrist/OpinionatedDocReviewer.git /opt/OpinionatedDocReviewer
cd /opt/OpinionatedDocReviewer/backend && uv sync --locked
cd /opt/OpinionatedDocReviewer/frontend && bun install --frozen-lockfile && bun run build
```

4. Create runtime env file:

```bash
sudo mkdir -p /etc/opinionated-doc-reviewer
sudo tee /etc/opinionated-doc-reviewer/env >/dev/null <<'EOF'
PORT=8006
FRONTEND_PORT=3001
REDIS_URL=redis://127.0.0.1:6379/0
REVIEW_QUEUE_NAME=review-jobs
REVIEW_INLINE=false
LLM_PROVIDER=openai
OPENAI_API_KEY=replace-me
AUTH_MODE=header
CORS_ALLOW_ORIGINS=https://odr.zlyxy.me
ALLOWED_HOSTS=odr.zlyxy.me
TRUST_PROXY_HEADERS=true
PROXY_TRUSTED_IPS=*
EOF
```

5. Run setup script:

```bash
cd /opt/OpinionatedDocReviewer
sudo ./scripts/systemd/setup.sh \
  --user zob \
  --repo-root /opt/OpinionatedDocReviewer \
  --env-file /etc/opinionated-doc-reviewer/env \
  --enable-now
```

This installs:
- `/etc/systemd/system/opdr-backend.service`
- `/etc/systemd/system/opdr-worker.service`
- `/etc/systemd/system/opdr-frontend.service`

6. Manual enable/start alternative (if you omitted `--enable-now`):

```bash
sudo systemctl enable --now redis-server
sudo systemctl enable --now opdr-backend.service
sudo systemctl enable --now opdr-worker.service
sudo systemctl enable --now opdr-frontend.service
```

7. Verify:

```bash
systemctl status opdr-backend opdr-worker opdr-frontend --no-pager
journalctl -u opdr-worker -n 100 --no-pager
curl -sS http://127.0.0.1:8006/api/status
```

If review jobs remain `queued`, focus on `opdr-worker` logs first.
