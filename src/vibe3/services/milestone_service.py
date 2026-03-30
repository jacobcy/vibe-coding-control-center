"""Milestone service for fetching milestone orchestration context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vibe3.clients.github_client import GitHubClient


@dataclass(frozen=True)
class MilestoneContext:
    """Aggregated milestone context for a task issue."""

    number: int
    title: str
    open_count: int
    closed_count: int
    issues: list[dict[str, Any]]
    task_issue_number: int


class MilestoneService:
    """Service for fetching milestone data from GitHub."""

    def __init__(self, github: GitHubClient | None = None) -> None:
        self._github = github or GitHubClient()

    def get_milestone_context(self, issue_number: int) -> MilestoneContext | None:
        """Fetch milestone orchestration context for a task issue.

        Args:
            issue_number: GitHub issue number

        Returns:
            MilestoneContext if issue has milestone, None otherwise
        """
        try:
            issue = self._github.view_issue(issue_number)
            if not isinstance(issue, dict) or not issue.get("milestone"):
                return None

            ms = issue["milestone"]
            ms_issues = self._github.get_milestone_issues(ms["number"])
        except (FileNotFoundError, RuntimeError):
            return None

        open_count = sum(
            1 for i in ms_issues if str(i.get("state", "")).upper() == "OPEN"
        )
        closed_count = sum(
            1 for i in ms_issues if str(i.get("state", "")).upper() == "CLOSED"
        )

        return MilestoneContext(
            number=ms["number"],
            title=ms["title"],
            open_count=open_count,
            closed_count=closed_count,
            issues=ms_issues,
            task_issue_number=issue_number,
        )
