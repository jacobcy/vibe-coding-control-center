"""Task failed resume usecase - bulk resume operations for failed issues."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibe3.services.issue_failure_service import (
    resume_failed_issue_to_handoff,
    resume_failed_issue_to_ready,
)

if TYPE_CHECKING:
    from vibe3.services.status_query_service import StatusQueryService


class TaskFailedResumeUsecase:
    """Orchestrates bulk resume operations for failed issues."""

    def __init__(
        self,
        status_service: "StatusQueryService",
        failure_service: object,
    ) -> None:
        """Initialize with required services.

        Args:
            status_service: Service for querying issue status
            failure_service: Service for issue state transitions
        """
        self.status_service = status_service
        self.failure_service = failure_service

    def resume_failed_issues(
        self,
        issue_numbers: list[int],
        reason: str,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Resume failed issues to ready or handoff based on plan_ref.

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
        # Fetch candidates
        candidates = self.status_service.fetch_failed_resume_candidates(flows=[])

        # Build candidate lookup
        candidate_map = {c["number"]: c for c in candidates}

        result: dict[str, Any] = {
            "resumed": [],
            "skipped": [],
            "requested": len(issue_numbers),
        }

        if dry_run:
            result["candidates"] = []

        for issue_number in issue_numbers:
            # Check if issue is in candidates
            if issue_number not in candidate_map:
                result["skipped"].append(
                    {
                        "issue_number": issue_number,
                        "reason": f"Issue #{issue_number} not in failed state",
                    }
                )
                continue

            candidate = candidate_map[issue_number]

            if dry_run:
                result["candidates"].append(candidate)
                continue

            # Defensive check: verify issue is still open + failed
            github_client = getattr(self.status_service, "github", None)
            if github_client:
                issue = github_client.view_issue(issue_number)
                if not isinstance(issue, dict):
                    result["skipped"].append(
                        {
                            "issue_number": issue_number,
                            "reason": "Failed to verify issue state",
                        }
                    )
                    continue

                # Check labels
                labels = issue.get("labels", [])
                if not any(
                    isinstance(label, dict) and label.get("name") == "state/failed"
                    for label in labels
                ):
                    result["skipped"].append(
                        {
                            "issue_number": issue_number,
                            "reason": "Issue no longer in failed state",
                        }
                    )
                    continue

            # Route based on plan_ref
            flow = candidate.get("flow")
            plan_ref = getattr(flow, "plan_ref", None) if flow else None

            if plan_ref:
                # Has plan_ref -> resume to handoff
                resume_failed_issue_to_handoff(
                    issue_number=issue_number,
                    repo=None,
                    reason=reason,
                    actor="human:resume",
                )
            else:
                # No plan_ref -> resume to ready
                resume_failed_issue_to_ready(
                    issue_number=issue_number,
                    repo=None,
                    reason=reason,
                    actor="human:resume",
                )

            result["resumed"].append(issue_number)

        return result
