from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.reviews.git_repo import _run_git


@dataclass
class GitCommit:
    sha: str
    message: str
    authored_at: datetime


def list_commits(repo_path: Path, limit: int = 50) -> list[GitCommit]:
    if not (repo_path / ".git").exists():
        return []
    format_str = "%H|%ct|%s"
    output = _run_git(["log", f"--max-count={limit}", f"--pretty={format_str}"], cwd=repo_path)
    commits: list[GitCommit] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        sha, ts, message = line.split("|", 2)
        commits.append(
            GitCommit(
                sha=sha,
                message=message,
                authored_at=datetime.fromtimestamp(int(ts), tz=timezone.utc),
            )
        )
    return commits
