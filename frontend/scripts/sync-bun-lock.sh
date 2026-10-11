#!/usr/bin/env bash
set -euo pipefail

mode=${1:-write}
if [[ "$mode" != write && "$mode" != --check ]]; then
  echo "Usage: $0 [--check]" >&2
  exit 2
fi
frontend=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
node --input-type=module - "$frontend" <<'NODE'
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
const directory = process.argv[2];
const manifest = JSON.parse(readFileSync(`${directory}/package.json`, "utf8"));
const lock = JSON.parse(readFileSync(`${directory}/package-lock.json`, "utf8"));
assert.equal(lock.lockfileVersion, 3, "Expected npm lockfile version 3");
for (const field of ["dependencies", "devDependencies", "optionalDependencies"]) {
  assert.deepEqual(lock.packages?.[""]?.[field] ?? {}, manifest[field] ?? {},
    `package-lock.json ${field} is stale; regenerate it with npm first`);
}
NODE
if [[ "$(bun --version)" != 1.4.3 ]]; then
  echo "Use Bun 1.4.3 to generate the same lockfile as CI." >&2
  exit 1
fi
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT
cp "$frontend/package.json" "$frontend/package-lock.json" "$temporary/"
(
  cd "$temporary"
  # npm validates overrides and transitive resolutions, not just root specs.
  npm ci --dry-run --ignore-scripts --no-audit --no-fund
  bun install --lockfile-only --ignore-scripts
)
bun "$frontend/scripts/check-lock-inventory.mjs" "$temporary/package-lock.json" "$temporary/bun.lock"
if [[ "$mode" == --check ]]; then
  if ! cmp -s "$frontend/bun.lock" "$temporary/bun.lock"; then
    echo "bun.lock differs from the npm resolution. Run bash scripts/sync-bun-lock.sh and commit both lockfiles." >&2
    exit 1
  fi
  echo "npm and Bun lockfiles are aligned."
else
  cp "$temporary/bun.lock" "$frontend/bun.lock"
fi
