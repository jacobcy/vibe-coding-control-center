"""Centralized dependency resolution service.

This module provides a single source of truth for checking whether
dependency issues are resolved across all code paths:
- QualifyGateService (queue dispatch)
- TaskResumeCandidates (manual resume)
- CheckService (consistency checks)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient


@dataclass(frozen=True)
class DependencyResolution:
    """Result of checking whether a dependency issue is resolved."""

    resolved: bool
    issue_number: int
    github_state: str | None = None  # "OPEN" | "CLOSED" | None


class DependencyResolutionService:
    """Service for checking dependency issue resolution status."""

    @staticmethod
    def is_dependency_resolved(
        issue_number: int,
        *,
        github_client: "GitHubClient",
        repo: str | None = None,
    ) -> DependencyResolution:
        """Check if a dependency issue is resolved.

        Resolution logic (in order):
        1. If GitHub issue state is "CLOSED" → resolved
        2. If issue has a merged PR → resolved
        3. Otherwise → unresolved

        Args:
            issue_number: GitHub issue number
            github_client: GitHub client for API calls
            repo: Optional repository (owner/repo format)

        Returns:
            DependencyResolution with resolution status and evidence
        """
        # Step 1: Fetch issue state
        issue_data = github_client.view_issue(issue_number, repo=repo, fields=["state"])

        # Handle error cases (fail-safe)
        if issue_data is None or issue_data == "network_error":
            logger.bind(
                domain="dependency_resolution",
                issue_number=issue_number,
                error="network_error" if issue_data == "network_error" else "not_found",
            ).warning(f"Cannot verify dependency #{issue_number}")
            return DependencyResolution(
                resolved=False,
                issue_number=issue_number,
                github_state=None,
            )

        if not isinstance(issue_data, dict):
            logger.bind(
                domain="dependency_resolution",
                issue_number=issue_number,
                result_type=type(issue_data).__name__,
            ).warning(f"Unexpected result type for #{issue_number}")
            return DependencyResolution(
                resolved=False,
                issue_number=issue_number,
                github_state=None,
            )

        # Extract state
        github_state = issue_data.get("state")

        # Step 2: Check if issue is closed
        if github_state == "CLOSED":
            return DependencyResolution(
                resolved=True,
                issue_number=issue_number,
                github_state=github_state,
            )

        # Step 3: Check for merged PR
        try:
            from vibe3.clients import get_merged_pr_for_issue

            pr_data = get_merged_pr_for_issue(issue_number, repo)
            if pr_data:
                return DependencyResolution(
                    resolved=True,
                    issue_number=issue_number,
                    github_state=github_state,
                )
        except Exception as e:
            logger.bind(
                domain="dependency_resolution",
                issue_number=issue_number,
                error=str(e),
            ).warning(f"Failed to check merged PR for #{issue_number}")

        # Step 4: Issue is unresolved
        return DependencyResolution(
            resolved=False,
            issue_number=issue_number,
            github_state=github_state,
        )
