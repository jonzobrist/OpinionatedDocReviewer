import assert from "node:assert/strict";
import { test } from "node:test";
import { assertSameInventory } from "./check-lock-inventory.mjs";

const npmLock = { packages: {
  "": {},
  "node_modules/sharp": { version: "0.35.5", integrity: "sha512-example" },
  "node_modules/next/node_modules/sharp": { version: "0.35.5", integrity: "sha512-example" },
} };
const bunLock = { packages: { sharp: ["sharp@0.35.5", "", {}, "sha512-example"] } };

test("allows deduplication without changing audited versions", () => {
  assertSameInventory(npmLock, bunLock);
});
test("rejects a silently re-resolved package", () => {
  const changed = structuredClone(bunLock);
  changed.packages.sharp[0] = "sharp@0.35.6";
  assert.throws(() => assertSameInventory(npmLock, changed));
});
test("rejects a changed integrity hash", () => {
  const changed = structuredClone(bunLock);
  changed.packages.sharp[3] = "sha512-other";
  assert.throws(() => assertSameInventory(npmLock, changed));
});
test("rejects omitted optional packages", () => {
  assert.throws(() => assertSameInventory(npmLock, { packages: {} }));
});

test("accepts actual legacy npm entry shape without integrity", () => {
  const npm = { packages: {
    "": {},
    "node_modules/@adobe/css-tools": { version: "4.4.4", dev: true, license: "MIT" },
  } };
  const bun = { packages: {
    "@adobe/css-tools": ["@adobe/css-tools@4.4.4", "", {}, "sha512-example"],
  } };
  assertSameInventory(npm, bun);
  bun.packages["@adobe/css-tools"][0] = "@adobe/css-tools@4.4.5";
  assert.throws(() => assertSameInventory(npm, bun));
});

test("rejects missing Bun hash when npm records integrity", () => {
  const changed = structuredClone(bunLock);
  changed.packages.sharp.pop();
  assert.throws(() => assertSameInventory(npmLock, changed));
});
