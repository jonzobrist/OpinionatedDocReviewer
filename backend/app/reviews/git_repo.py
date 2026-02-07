from __future__ import annotations

import os
import subprocess
from pathlib import Path

from app.core.config import settings


def ensure_repo(tenant_id: str, document_id: int) -> Path:
    root = Path(settings.DOC_REPO_ROOT).expanduser()
    repo_path = root / tenant_id / f"doc-{document_id}"
    repo_path.mkdir(parents=True, exist_ok=True)
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        _run_git(["init"], cwd=repo_path)
        _run_git(["config", "user.email", "reviews@local"], cwd=repo_path)
        _run_git(["config", "user.name", "OpinionatedDocReviewer"], cwd=repo_path)
    return repo_path


def write_and_commit(repo_path: Path, content: str, message: str) -> str:
    doc_path = repo_path / "document.md"
    doc_path.write_text(content, encoding="utf-8")
    _run_git(["add", str(doc_path.name)], cwd=repo_path)
    try:
        _run_git(["commit", "-m", message], cwd=repo_path)
    except subprocess.CalledProcessError as exc:
        stdout = (exc.stdout or "").lower()
        stderr = (exc.stderr or "").lower()
        if "nothing to commit" not in stdout and "nothing to commit" not in stderr:
            raise
    sha = _run_git(["rev-parse", "HEAD"], cwd=repo_path).strip()
    return sha


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout
