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
- All endpoints require `X-Tenant-Id` header (temporary placeholder for auth).
- Port is configurable via `PORT` (default `8006`).
- Configure provider via `LLM_PROVIDER=openai|bedrock`.
- OpenAI: set `OPENAI_API_KEY`.
- Bedrock: set `BEDROCK_MODEL_ID`, `BEDROCK_REGION`, and AWS credentials (env/IAM role or Bedrock-specific keys).
- Review jobs are enqueued to Redis and processed by the worker.
- Document versions are committed to a per-document git repository under `.run/doc-repos` (configurable via `DOC_REPO_ROOT`).

## Tests
```bash
pytest
```
