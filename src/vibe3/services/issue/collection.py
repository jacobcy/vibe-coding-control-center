"""Shared issue collection service."""

from __future__ import annotations

from vibe3.clients import GitHubClient
from vibe3.models import IssueInfo


class IssueCollectionService:
    """Collect open GitHub issues once and normalize them for consumers."""

    def __init__(self, github: GitHubClient, repo: str | None = None) -> None:
        self._github = github
        self._repo = repo

    def collect_open_issues(self, limit: int = 100) -> list[IssueInfo]:
        raw_issues = self._github.list_issues(
            limit=limit,
            state="open",
            assignee=None,
            repo=self._repo,
        )

        issues: list[IssueInfo] = []
        for item in raw_issues:
            issue = IssueInfo.from_github_payload(item)
            if issue is not None:
                issues.append(issue)
        return issues
