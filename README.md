# OpinionatedDocReviewer

OpinionatedDocReviewer is a document review application that runs multiple AI personas in parallel, anchors comments to document text, and displays live reviewer feedback in a professional UI.

## What It Does

- Upload `.md` and `.txt` documents with drag-and-drop.
- Auto-creates a document + version on upload.
- Runs persona reviews and streams comments into the live feed.
- Highlights commented sections and links them visually to feed comments.
- Saves review runs by document version.
- Supports manual re-review as an explicit override action.

## Stack

- Frontend: Next.js (React, TypeScript)
- Backend: FastAPI (Python)
- Queue/Workers: Redis + RQ
- Local persistence: SQLite (current local dev setup)
- Document/review artifact history: Git-backed local repos under `.run/doc-repos`

## Quick Start

### 1. Start dependencies

Make sure Redis is running (for queued reviews):

```bash
brew services start redis
```

### 2. Start the app

From repo root:

```bash
./scripts/admin/start.sh
```

Useful scripts:

- `./scripts/admin/status.sh`
- `./scripts/admin/restart.sh`
- `./scripts/admin/stop.sh`

### 3. Open UI

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8006/api`

## UI Routes

The app now uses path-based navigation. Refresh keeps you on the same page:

- Home: `/`
- Library: `/library`
- Agents: `/agents`
- History: `/history`
- System: `/system`
- Admin: `/admin`

Home supports deep links to a document:

- `/?doc=<document_id>`: open that document on load
- `/?doc=<document_id>&run=1`: open and start a review run once, then normalize URL back to `/?doc=<document_id>`

Top-left brand icon always navigates back to home (`/`).

## Testing

Backend:

```bash
cd backend
uv sync --extra test
uv run pytest
```

Frontend:

```bash
cd frontend
npm test -- --run
```

## Environment

Do not commit secrets.

- Root `.env` and `backend/.env` are gitignored.
- Configure provider settings via the UI: `System` panel in `http://localhost:3000`.
- Or configure via `backend/.env` / `backend/config.toml` (examples in `backend/.env.example` and `backend/config.example.toml`).
- CORS is configurable in backend env/config; see `PRODUCT.md`.

## LLM Provider Setup

The app supports two review providers:

- `openai`
- `bedrock` (AWS Bedrock)

Set provider:

```bash
LLM_PROVIDER=openai
# or
LLM_PROVIDER=bedrock
```

After changes, restart:

```bash
./scripts/admin/restart.sh
```

### OpenAI Configuration

Required:

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Optional tuning:

```bash
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=700
OPENAI_TEMPERATURE=0.2
OPENAI_TIMEOUT_SECONDS=30
```

Official docs:

- OpenAI API keys: [OpenAI API Keys](https://platform.openai.com/api-keys)
- OpenAI Responses API: [Responses API](https://platform.openai.com/docs/api-reference/responses)
- Model reference: [OpenAI Models](https://platform.openai.com/docs/models)

### AWS Bedrock Configuration

Required:

```bash
LLM_PROVIDER=bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
BEDROCK_REGION=us-east-1
```

Credentials (choose one):

- Standard AWS credential chain (recommended): IAM role, `~/.aws/credentials`, SSO, etc.
- Explicit env values:

```bash
BEDROCK_AWS_ACCESS_KEY_ID=...
BEDROCK_AWS_SECRET_ACCESS_KEY=...
BEDROCK_AWS_SESSION_TOKEN=... # optional
```

Official docs:

- Bedrock user guide: [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- Bedrock model IDs/availability: [Supported foundation models in Amazon Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/foundation-models-reference.html)
- Bedrock Converse API: [Converse API](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html)
- AWS credentials: [Boto3 Credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html)

## Meta Reviewer Calibration

Meta Reviewer synthesis priorities are calibrated as:

- `critical`: unsafe, incorrect, or security/compliance-dangerous content
- `high`: materially misleading or likely to cause implementation mistakes
- `medium`: quality issues that should be improved
- `low`: stylistic or optional improvements

Categories:

- `structure`, `clarity`, `technical`, `security`, `accessibility`, `style`

Operational safeguards:

- Input guardrails cap source comments/groups for a single synthesis run.
- If synthesis fails, API returns a clear error and fallback unsynthesized mode is available.
- Meta runs log structured completion/failure entries with tenant/version/job context and duration.

## GitHub Push Notes

If branch/upstream errors appear:

```bash
git branch -M main
git remote add origin git@github.com:<your-user>/<your-repo>.git
git push -u origin main
```

If `origin` already exists, update it:

```bash
git remote set-url origin git@github.com:<your-user>/<your-repo>.git
git push -u origin main
```
