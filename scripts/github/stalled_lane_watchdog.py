#!/usr/bin/env python3
"""Stalled lane watchdog for GitHub issues and pull requests.

Rules (configurable via constants/env):
- Rule A: issue labeled `state:in-progress` with no updates for > 8h.
- Rule B: open PR with checks green + reviewDecision REVIEW_REQUIRED and idle > 2h.
- Rule C: open PR with review comments and no commit/activity for > 8h.

Escalation behavior:
- Post concise comment prefixed with `WATCHDOG:` and next action recommendation.
- Anti-spam/idempotency guard: do not post another watchdog comment on the same
  target within 24h.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

# -----------------------------
# Configurable constants
# -----------------------------
WATCHDOG_PREFIX = "WATCHDOG:"
WATCHDOG_MARKER = "<!-- watchdog:stalled-lane -->"

RULE_A_LABEL = "state:in-progress"
RULE_A_IDLE_HOURS = float(os.getenv("WATCHDOG_RULE_A_HOURS", "8"))
RULE_B_IDLE_HOURS = float(os.getenv("WATCHDOG_RULE_B_HOURS", "2"))
RULE_C_IDLE_HOURS = float(os.getenv("WATCHDOG_RULE_C_HOURS", "8"))
COMMENT_COOLDOWN_HOURS = float(os.getenv("WATCHDOG_COMMENT_COOLDOWN_HOURS", "24"))

SEARCH_PAGE_SIZE = 100
ISSUE_COMMENTS_PAGE_SIZE = 100
GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class Candidate:
    number: int
    url: str
    title: str
    rule: str
    reason: str
    recommendation: str


class GitHubClient:
    def __init__(self, repo: str, token: str, dry_run: bool = False) -> None:
        self.repo = repo
        self.token = token
        self.dry_run = dry_run

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url=f"{GITHUB_API}{path}",
            method=method,
            data=body,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "odr-stalled-lane-watchdog",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API request failed [{method} {path}] {exc.code}: {detail}"
            ) from exc

    def graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        payload = {"query": query, "variables": variables}
        data = self._request("POST", "/graphql", payload)
        if data is None:
            raise RuntimeError("GraphQL returned empty response")
        if "errors" in data:
            raise RuntimeError(f"GraphQL errors: {json.dumps(data['errors'])}")
        return data["data"]

    def list_issue_comments(self, number: int) -> list[dict[str, Any]]:
        path = (
            f"/repos/{self.repo}/issues/{number}/comments"
            f"?per_page={ISSUE_COMMENTS_PAGE_SIZE}&sort=created&direction=desc"
        )
        return self._request("GET", path) or []

    def create_issue_comment(self, number: int, body: str) -> dict[str, Any] | None:
        if self.dry_run:
            return None
        path = f"/repos/{self.repo}/issues/{number}/comments"
        return self._request("POST", path, {"body": body})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect and escalate stalled lanes on GitHub")
    parser.add_argument(
        "--repo",
        default=os.getenv("GITHUB_REPOSITORY"),
        help="GitHub repository in owner/name format (default: GITHUB_REPOSITORY)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and print escalations without posting comments",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="GitHub token (default: GH_TOKEN/GITHUB_TOKEN/gh auth token)",
    )
    return parser.parse_args()


def resolve_token(explicit_token: str | None) -> str:
    if explicit_token:
        return explicit_token

    for env_name in ("GH_TOKEN", "GITHUB_TOKEN"):
        token = os.getenv(env_name)
        if token:
            return token

    try:
        output = subprocess.check_output(
            ["gh", "auth", "token"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        if output:
            return output
    except Exception:
        pass

    raise RuntimeError(
        "Missing GitHub token. Set GH_TOKEN or GITHUB_TOKEN, or pass --token."
    )


def parse_ts(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def hours_since(ts: dt.datetime, now: dt.datetime) -> float:
    return (now - ts).total_seconds() / 3600.0


def query_all_nodes(client: GitHubClient, search_query: str, node_fragment: str) -> list[dict[str, Any]]:
    query = f"""
    query($q: String!, $cursor: String) {{
      search(query: $q, type: ISSUE, first: {SEARCH_PAGE_SIZE}, after: $cursor) {{
        pageInfo {{
          hasNextPage
          endCursor
        }}
        nodes {{
          {node_fragment}
        }}
      }}
    }}
    """

    results: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        data = client.graphql(query, {"q": search_query, "cursor": cursor})
        search = data["search"]
        nodes = [node for node in search["nodes"] if node]
        results.extend(nodes)

        if not search["pageInfo"]["hasNextPage"]:
            break
        cursor = search["pageInfo"]["endCursor"]

    return results


def fetch_in_progress_issues(client: GitHubClient) -> list[dict[str, Any]]:
    search_query = f'repo:{client.repo} is:issue is:open label:"{RULE_A_LABEL}"'
    node_fragment = """
      ... on Issue {
        number
        title
        url
        updatedAt
      }
    """
    return query_all_nodes(client, search_query, node_fragment)


def fetch_open_pull_requests(client: GitHubClient) -> list[dict[str, Any]]:
    search_query = f"repo:{client.repo} is:pr is:open"
    node_fragment = """
      ... on PullRequest {
        number
        title
        url
        updatedAt
        reviewDecision
        reviewThreads(first: 1) {
          totalCount
        }
        commits(last: 1) {
          nodes {
            commit {
              committedDate
              statusCheckRollup {
                state
              }
            }
          }
        }
      }
    """
    return query_all_nodes(client, search_query, node_fragment)


def latest_pr_activity(pr: dict[str, Any]) -> dt.datetime:
    updated = parse_ts(pr["updatedAt"])

    commit_nodes = ((pr.get("commits") or {}).get("nodes") or [])
    if not commit_nodes:
        return updated

    committed = parse_ts(commit_nodes[-1]["commit"]["committedDate"])
    return max(updated, committed)


def status_rollup_state(pr: dict[str, Any]) -> str | None:
    commit_nodes = ((pr.get("commits") or {}).get("nodes") or [])
    if not commit_nodes:
        return None

    rollup = commit_nodes[-1]["commit"].get("statusCheckRollup")
    if not rollup:
        return None

    return rollup.get("state")


def build_candidates(client: GitHubClient, now: dt.datetime) -> list[Candidate]:
    candidates: list[Candidate] = []

    for issue in fetch_in_progress_issues(client):
        idle_h = hours_since(parse_ts(issue["updatedAt"]), now)
        if idle_h <= RULE_A_IDLE_HOURS:
            continue

        candidates.append(
            Candidate(
                number=issue["number"],
                url=issue["url"],
                title=issue["title"],
                rule="A",
                reason=(
                    f"Issue is labeled `{RULE_A_LABEL}` and has no updates for "
                    f"{idle_h:.1f}h (threshold: > {RULE_A_IDLE_HOURS:g}h)."
                ),
                recommendation=(
                    "Post a brief status update and either continue execution, "
                    f"switch to `state:blocked`, or remove `{RULE_A_LABEL}` if paused."
                ),
            )
        )

    for pr in fetch_open_pull_requests(client):
        activity_h = hours_since(latest_pr_activity(pr), now)
        review_decision = pr.get("reviewDecision")
        rollup_state = status_rollup_state(pr)
        review_threads = ((pr.get("reviewThreads") or {}).get("totalCount") or 0)

        if (
            rollup_state == "SUCCESS"
            and review_decision == "REVIEW_REQUIRED"
            and activity_h > RULE_B_IDLE_HOURS
        ):
            candidates.append(
                Candidate(
                    number=pr["number"],
                    url=pr["url"],
                    title=pr["title"],
                    rule="B",
                    reason=(
                        "PR checks are green (`statusCheckRollup=SUCCESS`) and "
                        "`reviewDecision=REVIEW_REQUIRED`, with no new activity for "
                        f"{activity_h:.1f}h (threshold: > {RULE_B_IDLE_HOURS:g}h)."
                    ),
                    recommendation=(
                        "Request/assign a reviewer (or maintainer handoff) and resolve "
                        "the review gate so merge/close can proceed."
                    ),
                )
            )
            continue

        if review_threads > 0 and activity_h > RULE_C_IDLE_HOURS:
            candidates.append(
                Candidate(
                    number=pr["number"],
                    url=pr["url"],
                    title=pr["title"],
                    rule="C",
                    reason=(
                        f"PR has review comments/threads ({review_threads}) and no "
                        f"commit/activity for {activity_h:.1f}h "
                        f"(threshold: > {RULE_C_IDLE_HOURS:g}h)."
                    ),
                    recommendation=(
                        "Push a follow-up commit or post a response/update on review "
                        "comments to unblock the lane."
                    ),
                )
            )

    return candidates


def has_recent_watchdog_comment(
    client: GitHubClient, number: int, now: dt.datetime
) -> tuple[bool, str | None]:
    cooldown = dt.timedelta(hours=COMMENT_COOLDOWN_HOURS)
    cutoff = now - cooldown

    comments = client.list_issue_comments(number)
    for comment in comments:
        created_at_raw = comment.get("created_at")
        if not created_at_raw:
            continue

        created_at = parse_ts(created_at_raw)
        # comments are requested in descending create-time order
        if created_at < cutoff:
            break

        body = comment.get("body") or ""
        if WATCHDOG_MARKER in body:
            return True, created_at.isoformat()

    return False, None


def render_comment(candidate: Candidate) -> str:
    return (
        f"{WATCHDOG_PREFIX} potential stalled lane detected (Rule {candidate.rule}).\n\n"
        f"{candidate.reason}\n\n"
        f"Recommended next action: {candidate.recommendation}\n\n"
        f"_Automated watchdog nudge; duplicate comments are suppressed for "
        f"{COMMENT_COOLDOWN_HOURS:g}h._\n"
        f"{WATCHDOG_MARKER}"
    )


def main() -> int:
    args = parse_args()

    if not args.repo or "/" not in args.repo:
        print(
            "error: --repo is required in owner/name format "
            "(or set GITHUB_REPOSITORY)",
            file=sys.stderr,
        )
        return 2

    try:
        token = resolve_token(args.token)
        client = GitHubClient(repo=args.repo, token=token, dry_run=args.dry_run)

        now = dt.datetime.now(dt.timezone.utc)
        candidates = build_candidates(client, now)

        print(
            f"[watchdog] scanned repo={args.repo} candidates={len(candidates)} "
            f"dry_run={args.dry_run}"
        )

        posted = 0
        skipped = 0
        for candidate in candidates:
            recently_posted, created_at = has_recent_watchdog_comment(
                client, candidate.number, now
            )
            if recently_posted:
                skipped += 1
                print(
                    f"[watchdog] skip #{candidate.number} rule={candidate.rule} "
                    f"(cooldown active; previous watchdog comment at {created_at})"
                )
                continue

            body = render_comment(candidate)
            if args.dry_run:
                print(
                    f"[watchdog] dry-run would comment on #{candidate.number} "
                    f"rule={candidate.rule} url={candidate.url}"
                )
                print(body)
            else:
                response = client.create_issue_comment(candidate.number, body)
                comment_url = (response or {}).get("html_url", "<unknown>")
                print(
                    f"[watchdog] commented on #{candidate.number} rule={candidate.rule} "
                    f"comment={comment_url}"
                )

            posted += 1

        print(
            f"[watchdog] done posted={posted} skipped_by_cooldown={skipped} "
            f"total_candidates={len(candidates)}"
        )
        return 0

    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
