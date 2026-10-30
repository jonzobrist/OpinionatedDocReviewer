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
- `NEXT_PUBLIC_API_BASE` is the primary API base setting (used by browser calls and by Next.js `/api` rewrite when present).
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


## Dependency updates

Use Bun 1.4.3 (matching CI). Keep both lockfiles in every dependency PR:

```bash
npm install --package-lock-only --ignore-scripts
bash scripts/sync-bun-lock.sh
bash scripts/sync-bun-lock.sh --check
bun install --frozen-lockfile
npm ls --all
bun run typecheck
bun run test
bun run build
npm audit --audit-level=low
```

`package-lock.json` is the resolution source; `sync-bun-lock.sh` imports it in a
clean temporary directory to generate `bun.lock`. It uses an npm dry-run as an
additional installability check and verifies every imported package version against
npm, plus integrity hashes wherever npm records them. Legacy npm entries without
integrity get version parity checks only. This verifies the package inventory,
not identical hoisting or dependency-edge placement. CI checks the generated file
before installing so security audits and Bun execution use matching resolutions.
Do not hand-edit integrity hashes or resolved lockfile entries.

The sharp override keeps Next.js image processing on sharp 0.35.4 or newer within
the compatible 0.35 series. Node-based installs need Node >=20.9 for sharp; the
current Vite test toolchain additionally requires Node >=20.19 or >=22.12.

Security overrides keep PostCSS on its patched 8.x line without requiring a
Next.js major upgrade, and keep Vite on the compatible 7.x test toolchain with
patched esbuild. Mermaid stays on the patched 11.16 line; its KaTeX dependency
is pinned to patched 0.18.2 (later patches require a newer Node CLI dependency),
while UUID remains on patched 11.x. DOMPurify is
bounded to patched 3.x rather than accepting an untested future major.
`tests/mermaidDiagram.test.tsx` exercises the real renderer, math labels, malicious
HTML/link sanitization, and invalid-diagram fallback after these upgrades.

After the frozen Bun install, CI also runs `npm ls --all` to reject invalid
installed dependencies or overrides. An npm dry-run alone can exit successfully
with warnings for some stale override resolutions.
