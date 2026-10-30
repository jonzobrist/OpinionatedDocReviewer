"""Regression tests for deterministic npm-to-Bun lockfile synchronization."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class LockfileSyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        source = Path(__file__).resolve().parents[2] / "frontend/scripts/sync-bun-lock.sh"
        self.script = self.root / "scripts/sync-bun-lock.sh"
        shutil.copyfile(source, self.script)
        for name in ("package.json", "package-lock.json"):
            (self.root / name).write_text("{}\n")
        (self.root / "package-lock.json").write_text('{"lockfileVersion":3,"packages":{"":{}}}\n')
        self.lock = self.root / "bun.lock"
        self.lock.write_text("old lock\n")
        self.expected = self.root / "expected.lock"
        self.expected.write_text("generated lock\n")
        binary = self.root / "bin"
        binary.mkdir()
        bun = binary / "bun"
        bun.write_text('#!/usr/bin/env bash\nset -eu\n'
                       'if [[ "$1" == --version ]]; then echo "${TEST_BUN_VERSION:-1.4.3}"; exit; fi\n'
                       'if [[ "$1" == */check-lock-inventory.mjs ]]; then exit; fi\n'
                       '[[ "$*" == "install --lockfile-only --ignore-scripts" ]]\n'
                       '[[ ! -e bun.lock && -f package.json && -f package-lock.json ]]\n'
                       'cp "$TEST_EXPECTED_LOCK" bun.lock\n')
        bun.chmod(0o755)
        npm = binary / "npm"
        npm.write_text('#!/usr/bin/env bash\nset -eu\n'
                       '[[ "$*" == "ci --dry-run --ignore-scripts --no-audit --no-fund" ]]\n'
                       'exit "${TEST_NPM_EXIT:-0}"\n')
        npm.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{binary}:{os.environ['PATH']}",
                        TEST_EXPECTED_LOCK=str(self.expected))

    def run_sync(self, *arguments):
        return subprocess.run(["bash", str(self.script), *arguments], env=self.env,
                              capture_output=True, text=True, check=False)

    def test_write_imports_in_clean_directory(self):
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.lock.read_text(), self.expected.read_text())

    def test_check_rejects_drift_without_modifying_lock(self):
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs", result.stderr)
        self.assertEqual(self.lock.read_text(), "old lock\n")

    def test_check_accepts_matching_lock(self):
        self.lock.write_text(self.expected.read_text())
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_wrong_bun_version(self):
        self.env["TEST_BUN_VERSION"] = "1.0.0"
        self.assertEqual(self.run_sync().returncode, 1)
        self.assertEqual(self.lock.read_text(), "old lock\n")

    def test_rejects_unknown_mode(self):
        self.assertEqual(self.run_sync("--unknown").returncode, 2)

    def test_rejects_stale_npm_manifest(self):
        (self.root / "package.json").write_text('{"dependencies":{"next":"15.5.27"}}\n')
        result = self.run_sync("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("package-lock.json dependencies is stale", result.stderr)

    def test_rejects_npm_override_validation_failure(self):
        self.env["TEST_NPM_EXIT"] = "1"
        result = self.run_sync()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.lock.read_text(), "old lock\n")


if __name__ == "__main__":
    unittest.main()
