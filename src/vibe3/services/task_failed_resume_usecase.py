"""Task failed resume usecase - bulk resume operations for failed issues.

DEPRECATED: Use TaskResumeUsecase instead.

This module is kept for backward compatibility and forwards to
the unified TaskResumeUsecase internally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibe3.services.task_resume_usecase import TaskResumeUsecase

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.services.flow_service import FlowService
    from vibe3.services.issue_flow_service import IssueFlowService
    from vibe3.services.label_service import LabelService
    from vibe3.services.status_query_service import StatusQueryService


class TaskFailedResumeUsecase:
    """Orchestrates bulk resume operations for failed issues.

    DEPRECATED: Use TaskResumeUsecase instead.
    """

    def __init__(
        self,
        status_service: "StatusQueryService",
        failure_service: object,
        label_service: "LabelService | None" = None,
        flow_service: "FlowService | None" = None,
        git_client: "GitClient | None" = None,
        github_client: "GitHubClient | None" = None,
        issue_flow_service: "IssueFlowService | None" = None,
    ) -> None:
        """Initialize with required services.

        DEPRECATED: Use TaskResumeUsecase instead.

        Args:
            status_service: Service for querying issue status
            failure_service: Service for issue state transitions (unused)
            label_service: Service for label operations (optional)
            flow_service: Service for flow operations (optional)
            git_client: Git client for worktree operations (optional)
            github_client: GitHub client for API operations (optional)
            issue_flow_service: Service for issue-flow mapping (optional)
        """
        self.status_service = status_service
        self.failure_service = failure_service
        # Pass all dependencies to unified usecase for proper mocking
        self._unified_usecase = TaskResumeUsecase(
            status_service=status_service,
            label_service=label_service,
            flow_service=flow_service,
            git_client=git_client,
            github_client=github_client,
            issue_flow_service=issue_flow_service,
        )

    def resume_failed_issues(
        self,
        issue_numbers: list[int],
        reason: str,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Resume failed issues to ready or handoff based on plan_ref.

        DEPRECATED: Use TaskResumeUsecase.resume_issues() instead.

        Args:
            issue_numbers: List of issue numbers to resume
            reason: Reason for resume (written to issue comments)
            dry_run: If True, only report what would be done without executing

        Returns:
            Dict with:
                - resumed: List of issue numbers that were resumed
                - skipped: List of dicts with issue_number and reason
                - requested: Total number of issues requested
                - candidates: List of candidate issues (dry-run only)
        """
        result = self._unified_usecase.resume_issues(
            issue_numbers=issue_numbers,
            reason=reason,
            dry_run=dry_run,
        )

        # Convert result format to match old API
        converted: dict[str, Any] = {
            "resumed": [r["number"] for r in result.get("resumed", [])],
            "skipped": [
                {"issue_number": s["number"], "reason": s["reason"]}
                for s in result.get("skipped", [])
            ],
            "requested": len(issue_numbers),  # Old API: count of requested issues
        }

        if dry_run:
            converted["candidates"] = result.get("candidates", [])

        return converted
