"""Ports for issue/pr state synchronization."""

from __future__ import annotations

import json
import subprocess
from typing import Protocol

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.pr import PRResponse


class IssueLabelPort(Protocol):
    """Port for issue label read/write operations."""

    def get_issue_labels(self, issue_number: int) -> list[str] | None:
        """Return issue labels; None means labels cannot be fetched."""
        ...

    def add_issue_label(self, issue_number: int, label: str) -> bool:
        """Add one label to issue."""
        ...

    def remove_issue_label(self, issue_number: int, label: str) -> bool:
        """Remove one label from issue."""
        ...


class PrStatePort(Protocol):
    """Port for PR fact confirmation and transition operations."""

    def get_pr(
        self, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        """Read PR fact by number or branch."""
        ...

    def mark_ready(self, pr_number: int) -> PRResponse:
        """Mark PR ready for review."""
        ...

    def merge_pr(self, pr_number: int) -> PRResponse:
        """Merge PR."""
        ...


class GhIssueLabelPort:
    """Default issue label port backed by `gh issue`."""

    def __init__(self, repo: str | None = None) -> None:
        self.repo = repo
        if self.repo is None:
            from vibe3.config.settings import VibeConfig

            config = VibeConfig.get_defaults()
            self.repo = getattr(getattr(config, "orchestra", None), "repo", None)

    def _build_cmd(self, base: list[str]) -> list[str]:
        cmd = list(base)
        if self.repo:
            cmd.extend(["--repo", self.repo])
        return cmd

    def get_issue_labels(self, issue_number: int) -> list[str] | None:
        try:
            result = subprocess.run(
                self._build_cmd(
                    ["gh", "issue", "view", str(issue_number), "--json", "labels"]
                ),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.bind(external="github", issue_number=issue_number).warning(
                "gh command not found"
            )
            return None

        if result.returncode != 0:
            logger.bind(
                external="github",
                issue_number=issue_number,
                error=result.stderr,
            ).warning("Failed to fetch issue labels")
            return None

        data = json.loads(result.stdout)
        labels = data.get("labels", [])
        return [label.get("name", "") for label in labels if label.get("name")]

    def add_issue_label(self, issue_number: int, label: str) -> bool:
        try:
            result = subprocess.run(
                self._build_cmd(
                    ["gh", "issue", "edit", str(issue_number), "--add-label", label]
                ),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.bind(
                external="github", issue_number=issue_number, label=label
            ).warning("gh command not found")
            return False
        return result.returncode == 0

    def remove_issue_label(self, issue_number: int, label: str) -> bool:
        try:
            result = subprocess.run(
                self._build_cmd(
                    ["gh", "issue", "edit", str(issue_number), "--remove-label", label]
                ),
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.bind(
                external="github", issue_number=issue_number, label=label
            ).warning("gh command not found")
            return False
        return result.returncode == 0


class GitHubPrStatePort:
    """Default PR state port backed by GitHubClient."""

    def __init__(self, github_client: GitHubClient | None = None) -> None:
        self.github_client = github_client or GitHubClient()

    def get_pr(
        self, pr_number: int | None = None, branch: str | None = None
    ) -> PRResponse | None:
        return self.github_client.get_pr(pr_number=pr_number, branch=branch)

    def mark_ready(self, pr_number: int) -> PRResponse:
        return self.github_client.mark_ready(pr_number)

    def merge_pr(self, pr_number: int) -> PRResponse:
        return self.github_client.merge_pr(pr_number)
