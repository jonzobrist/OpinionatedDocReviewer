# Backend API

## Run (local)
```bash
python -m app.main
```

## Worker (reviews)
The API runs reviews inline by default for reliability (`REVIEW_INLINE=true`).
Workers are optional for scale; enable `REVIEW_INLINE=false` to use the queue.

Requires Redis (default `redis://localhost:6379/0`) and an LLM provider configuration.

```bash
python -m app.worker
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
pytest
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
