"""FailedGate: global freeze signal based on open state/failed issues."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, cast

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState


@dataclass(frozen=True)
class GateResult:
    """Result of a failed gate check."""

    blocked: bool
    issue_number: int | None = None
    issue_title: str | None = None
    reason: str | None = None
    comment_url: str | None = None

    @classmethod
    def open(cls) -> GateResult:
        """Create a non-blocking gate result."""
        return cls(blocked=False)


class FailedGate:
    """Orchestra failed state gate.

    Checks if there are any open issues with 'state/failed' label and extracts
    the failure reason from comments to provide a unified freeze signal.
    """

    def __init__(
        self, github: GitHubClient | None = None, repo: str | None = None
    ) -> None:
        self._github = github or GitHubClient()
        self._repo = repo

    def check(self) -> GateResult:
        """Check if orchestra dispatch should be frozen.

        Returns:
            GateResult: blocked=True if any state/failed issue is open.
        """
        log = logger.bind(domain="orchestra", action="failed_gate_check")
        log.debug("Checking for open state/failed issues")

        try:
            # 1. Search for open issues with state/failed label
            # We use gh issue list --label state/failed --state open
            # Note: list_issues might not support multiple labels in args
            # but we can pass via repo or use label filter if supported.
            # github_issues_ops.py list_issues lacks label param.
            # I should add it or use a custom gh command.

            issues = self._list_failed_issues()
            if not issues:
                return GateResult.open()

            # 2. Pick the first one (usually most recent or most relevant)
            issue = issues[0]
            issue_number = issue["number"]
            issue_title = issue.get("title", f"Issue #{issue_number}")

            log.info(f"Found open state/failed issue #{issue_number}: {issue_title}")

            # 3. Fetch comments to extract reason
            reason, comment_url = self._extract_reason(issue_number)

            return GateResult(
                blocked=True,
                issue_number=issue_number,
                issue_title=issue_title,
                reason=reason,
                comment_url=comment_url,
            )

        except Exception as exc:
            log.error(f"Failed to check failed gate: {exc}")
            # Fail-closed: If we cannot verify the repository state, we assume
            # it might be blocked to prevent accidental dispatches during
            # infrastructure or authentication issues.
            return GateResult(
                blocked=True,
                reason=f"failed gate check error: {exc}",
            )

    def _list_failed_issues(self) -> list[dict[str, Any]]:
        """List open issues with state/failed label using gh CLI."""
        import json
        import subprocess

        cmd = [
            "gh",
            "issue",
            "list",
            "--label",
            IssueState.FAILED.to_label(),
            "--state",
            "open",
            "--json",
            "number,title",
        ]
        if self._repo:
            cmd.extend(["--repo", self._repo])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            err = result.stderr.strip()
            logger.bind(domain="orchestra").warning(
                f"Failed to list failed issues: {err}"
            )
            raise RuntimeError(f"GitHub CLI error: {err}")

        return cast(list[dict[str, Any]], json.loads(result.stdout))

    def _extract_reason(self, issue_number: int) -> tuple[str, str | None]:
        """Extract failure reason from issue comments.

        Priority:
        1. Latest comment containing '原因:' or 'reason:'
        2. Latest comment from a manager/orchestra actor
        3. Latest comment overall (summary)
        """
        import json
        import subprocess

        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "comments",
        ]
        if self._repo:
            cmd.extend(["--repo", self._repo])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return "reason unavailable (failed to fetch comments)", None

        data = json.loads(result.stdout)
        comments = data.get("comments", [])
        if not comments:
            return "reason unavailable (no comments found)", None

        # Reverse to get latest first
        for comment in reversed(comments):
            body = comment.get("body", "")
            url = comment.get("url")

            # Look for explicit reason markers
            # Matches: 原因: xxx or reason: xxx (case insensitive)
            match = re.search(r"(?:原因|reason)[:：\s]+(.*)", body, re.IGNORECASE)
            if match:
                reason = match.group(1).strip()
                if reason:
                    # Multi-line: take first non-empty line
                    return reason.split("\n")[0].strip(), url

            # If no explicit marker, check if it looks like a failure report
            if "failed" in body.lower() or "error" in body.lower():
                # Take first 100 chars as summary
                summary = body.strip().split("\n")[0][:100]
                return f"{summary}...", url

        # Fallback to latest comment summary
        latest_body = comments[-1].get("body", "").strip().split("\n")[0][:100]
        return f"{latest_body}...", comments[-1].get("url")
