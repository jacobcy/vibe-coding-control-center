"""Task failed resume usecase - bulk resume operations for failed issues.

DEPRECATED: Use TaskResumeUsecase instead.

This module is kept for backward compatibility and forwards to
the unified TaskResumeUsecase internally.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibe3.services.task_resume_usecase import TaskResumeUsecase

if TYPE_CHECKING:
    from vibe3.services.status_query_service import StatusQueryService


class TaskFailedResumeUsecase:
    """Orchestrates bulk resume operations for failed issues.

    DEPRECATED: Use TaskResumeUsecase instead.
    """

    def __init__(
        self,
        status_service: "StatusQueryService",
        failure_service: object,
    ) -> None:
        """Initialize with required services.

        DEPRECATED: Use TaskResumeUsecase instead.

        Args:
            status_service: Service for querying issue status
            failure_service: Service for issue state transitions (unused)
        """
        self.status_service = status_service
        self.failure_service = failure_service
        self._unified_usecase = TaskResumeUsecase()

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
