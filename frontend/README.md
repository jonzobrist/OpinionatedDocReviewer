# OpinionatedDocReviewer Frontend

## Run (local)
```bash
bun install
bun run dev
```

## Tests
```bash
bun run test
```

## Notes
- Set `NEXT_PUBLIC_API_BASE` if the backend is not on the same origin at `/api`.
- The UI also lets you override API base + tenant ID in the Connection panel.
- Upload supports `.md`, `.markdown`, and `.txt` files (treated as Markdown).
- For single-domain reverse proxy setups (`https://<host>` with `/api/*` -> backend), you can leave `NEXT_PUBLIC_API_BASE` unset and the client will use `${window.location.origin}/api`.

API base resolution order:
1. `localStorage` key `odr_api_base` (System -> Client Connection)
2. `NEXT_PUBLIC_API_BASE`
3. Browser origin fallback: `${window.location.origin}/api`
