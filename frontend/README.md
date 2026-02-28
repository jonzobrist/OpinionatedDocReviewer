# OpinionatedDocReviewer Frontend

## Run (local)
```bash
bun install
# Optional port override:
# FRONTEND_PORT=3100 bun run dev
bun run dev
```

## Tests
```bash
bun run test
```

## Notes
- `NEXT_PUBLIC_API_BASE` is the primary API base setting (used by browser calls and by Next.js `/api` rewrite when present).
- Frontend port resolution for `bun run dev`/`bun run start`: `PORT` -> `FRONTEND_PORT` -> `3000`.
- Optional: set `NEXT_SERVER_API_BASE` only if the server-side rewrite target must differ from the public API base.
- If neither is set, defaults are `${window.location.origin}/api` (browser) and `http://localhost:8006/api` (server rewrite).
- For reverse proxy setups like `https://odr.zlyxy.me`, set `NEXT_PUBLIC_API_BASE=https://odr.zlyxy.me/api`.
- The UI also lets you override API base + tenant ID in the Connection panel.
- Meta reviewer/agent settings are editable in `System` (`/system`) and saved through `/api/settings`.
- Upload supports `.md`, `.markdown`, and `.txt` files (treated as Markdown).
- For single-domain reverse proxy setups (`https://<host>` with `/api/*` -> backend), you can leave `NEXT_PUBLIC_API_BASE` unset and the client will use `${window.location.origin}/api`.

API base resolution order:
1. `localStorage` key `odr_api_base` (System -> Client Connection)
2. `NEXT_PUBLIC_API_BASE`
3. Browser origin fallback: `${window.location.origin}/api`
