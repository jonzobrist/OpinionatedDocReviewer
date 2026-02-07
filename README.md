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
- Set `OPENAI_API_KEY` in local env file(s).
- CORS is configurable in backend env/config; see `PRODUCT.md`.

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

