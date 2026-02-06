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
- Set `NEXT_PUBLIC_API_BASE` if the backend is not on `http://localhost:8006/api`.
- The UI also lets you override API base + tenant ID in the Connection panel.
- Upload supports `.md`, `.markdown`, and `.txt` files (treated as Markdown).
