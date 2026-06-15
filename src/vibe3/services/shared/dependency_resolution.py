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
    merged_pr_number: int | None = None  # PR evidence when merged
    reason: str | None = None  # Human-readable summary for logs/skip messages


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
                reason=(
                    f"Dependency #{issue_number} could not be verified "
                    f"(network error or not found)"
                ),
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
                reason=f"Dependency #{issue_number} returned unexpected result",
            )

        # Extract state
        github_state = issue_data.get("state")

        # Step 2: Check if issue is closed
        if github_state == "CLOSED":
            return DependencyResolution(
                resolved=True,
                issue_number=issue_number,
                github_state=github_state,
                reason=f"Dependency #{issue_number} is CLOSED",
            )

        # Step 3: Check for merged PR
        try:
            from vibe3.clients import get_merged_pr_for_issue

            pr_data = get_merged_pr_for_issue(issue_number, repo)
            if pr_data:
                pr_number = pr_data.get("number") if pr_data else None

                return DependencyResolution(
                    resolved=True,
                    issue_number=issue_number,
                    github_state=github_state,
                    merged_pr_number=pr_number,
                    reason=(
                        f"Dependency #{issue_number} has merged PR #{pr_number}"
                        if pr_number
                        else f"Dependency #{issue_number} has merged PR"
                    ),
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
            reason=f"Dependency #{issue_number} is still {github_state or 'unknown'}",
        )
