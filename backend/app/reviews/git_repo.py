from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings
from app.security.tenant import validate_tenant_id


def _resolve_repo_path(tenant_id: str, document_id: int) -> tuple[Path, Path]:
    if document_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid document id")
    safe_tenant_id = validate_tenant_id(tenant_id)
    root = Path(settings.DOC_REPO_ROOT).expanduser().resolve()
    repo_path = (root / safe_tenant_id / f"doc-{document_id}").resolve()
    if not repo_path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid repository path")
    return root, repo_path


def ensure_repo(tenant_id: str, document_id: int) -> Path:
    _, repo_path = _resolve_repo_path(tenant_id, document_id)
    repo_path.mkdir(parents=True, exist_ok=True)
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        _run_git(["init"], cwd=repo_path)
        _run_git(["config", "user.email", "reviews@local"], cwd=repo_path)
        _run_git(["config", "user.name", "OpinionatedDocReviewer"], cwd=repo_path)
    return repo_path


def remove_repo(tenant_id: str, document_id: int) -> bool:
    """Remove the git-backed document repo for a deleted document.

    Prevents stale history from being inherited by a new document that
    reuses the same database id (e.g. SQLite rowid reuse after DELETE).
    Safe to call even when the repo does not yet exist.
    """
    root, repo_path = _resolve_repo_path(tenant_id, document_id)
    if not repo_path.exists():
        return False
    if not repo_path.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Invalid repository path")
    shutil.rmtree(repo_path, ignore_errors=False)
    return True


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
