# Backend API

## Run (local)
```bash
python -m app.main
```

## Worker (reviews)
The API runs reviews inline by default for reliability (`REVIEW_INLINE=true`).
Workers are optional for scale; enable `REVIEW_INLINE=false` to use the queue.

Requires Redis (default `redis://localhost:6379/0`) and an OpenAI API key.

```bash
python -m app.worker
```

## API Notes
- All endpoints require `X-Tenant-Id` header (temporary placeholder for auth).
- Port is configurable via `PORT` (default `8006`).
- Configure OpenAI via `OPENAI_API_KEY` env var or `backend/config.toml` (see `backend/config.example.toml`).
- Review jobs are enqueued to Redis and processed by the worker.
- Document versions are committed to a per-document git repository under `.run/doc-repos` (configurable via `DOC_REPO_ROOT`).

## Tests
```bash
pytest
```
