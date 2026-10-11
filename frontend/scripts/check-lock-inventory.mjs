import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Hoisting may differ between package managers; the audited package versions
// must not. Compare integrity only where npm recorded it; older lock entries
// may omit integrity. Compare all platforms, including optional dependencies.
export function assertSameInventory(npmLock, bunLock) {
  const npmInventory = new Set();
  const npmHashes = [];
  for (const [path, entry] of Object.entries(npmLock.packages)) {
    if (path === "") continue;
    assert.ok(entry.version && !entry.link,
      `Unsupported npm lock entry: ${path}`);
    const name = entry.name ?? path.split("node_modules/").at(-1);
    const identity = `${name}@${entry.version}`;
    npmInventory.add(identity);
    if (entry.integrity) npmHashes.push([identity, entry.integrity]);
  }
  const bunInventory = new Set();
  const bunHashes = new Set();
  for (const [path, entry] of Object.entries(bunLock.packages)) {
    assert.ok(Array.isArray(entry) && typeof entry[0] === "string",
      `Unsupported Bun lock entry: ${path}`);
    bunInventory.add(entry[0]);
    bunHashes.add(`${entry[0]} ${entry.at(-1)}`);
  }
  assert.deepEqual([...bunInventory].sort(), [...npmInventory].sort(),
    "Bun import changed npm package versions");
  for (const [identity, integrity] of npmHashes) {
    assert.ok(bunHashes.has(`${identity} ${integrity}`),
      `Bun import changed the recorded npm integrity for ${identity}`);
  }
}

if (import.meta.main) {
  const npmLock = JSON.parse(readFileSync(process.argv[2], "utf8"));
  const bunLock = Bun.JSONC.parse(readFileSync(process.argv[3], "utf8"));
  assertSameInventory(npmLock, bunLock);
}
