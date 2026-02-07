from __future__ import annotations

import json
from pathlib import Path

from app.reviews.git_repo import _run_git


def write_review_and_commit(
    repo_path: Path,
    version_id: int,
    review_job_id: int,
    payload: dict,
) -> str:
    review_dir = repo_path / ".reviews" / f"version-{version_id}"
    review_dir.mkdir(parents=True, exist_ok=True)
    file_path = review_dir / f"run-{review_job_id}.json"
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    rel_path = file_path.relative_to(repo_path)
    _run_git(["add", str(rel_path)], cwd=repo_path)
    _run_git(["commit", "-m", f"Review run {review_job_id} for version {version_id}"], cwd=repo_path)
    sha = _run_git(["rev-parse", "HEAD"], cwd=repo_path).strip()
    return sha
