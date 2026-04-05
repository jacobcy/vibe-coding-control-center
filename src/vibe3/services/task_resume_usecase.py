"""Unified task resume usecase.

Provides a single entry point for resuming tasks regardless of
whether they are in failed or blocked state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import (
    resume_blocked_issue_to_ready,
    resume_failed_issue_to_handoff,
    resume_failed_issue_to_ready,
)
from vibe3.services.label_service import LabelService
from vibe3.services.status_query_service import StatusQueryService

if TYPE_CHECKING:
    from vibe3.models.flow import FlowStatusResponse


class TaskResumeUsecase:
    """Unified usecase for resuming failed or blocked tasks."""

    def __init__(self) -> None:
        self.status_service = StatusQueryService()
        self.label_service = LabelService()
        self.flow_service = FlowService()

    def resume_issues(
        self,
        issue_numbers: list[int] | None = None,
        reason: str = "",
        dry_run: bool = False,
        flows: list[FlowStatusResponse] | None = None,
        stale_flows: list[FlowStatusResponse] | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        """Resume failed or blocked issues.

        Args:
            issue_numbers: Optional list of specific issue numbers to resume
            reason: Resume reason to include in comments
            dry_run: If True, only report candidates without mutating
            flows: Active flow status responses
            stale_flows: Stale flow status responses
            repo: Repository (owner/repo format, optional)

        Returns:
            Dict with:
                - resumed: List of successfully resumed issues
                - skipped: List of skipped issues with reasons
                - requested: List of requested issue numbers (if provided)
                - candidates: List of resumable candidates (dry-run only)
        """
        # Fetch candidates
        candidates = self.status_service.fetch_resume_candidates(
            flows=flows or [], stale_flows=stale_flows or []
        )

        # Filter by requested issue numbers if provided
        if issue_numbers:
            candidates = [c for c in candidates if c.get("number") in issue_numbers]

        result: dict[str, Any] = {
            "resumed": [],
            "skipped": [],
            "requested": issue_numbers if issue_numbers else [],
        }

        # Dry-run: return candidates without mutation
        if dry_run:
            result["candidates"] = candidates
            return result

        # Apply resume operations
        for candidate in candidates:
            issue_number = candidate.get("number")
            resume_kind = candidate.get("resume_kind")

            if not isinstance(issue_number, int) or not isinstance(resume_kind, str):
                continue

            # Defensive check: verify current state matches resume_kind
            if not self._verify_issue_state_for_resume(issue_number, resume_kind, repo):
                result["skipped"].append(
                    {
                        "number": issue_number,
                        "reason": f"不再处于 {resume_kind} 状态，跳过恢复",
                    }
                )
                continue

            # Route to appropriate resume function based on resume_kind
            try:
                if resume_kind == "failed":
                    flow = candidate.get("flow")
                    plan_ref = getattr(flow, "plan_ref", None) if flow else None

                    if plan_ref:
                        # Failed with plan -> handoff
                        resume_failed_issue_to_handoff(
                            issue_number=issue_number,
                            repo=repo,
                            reason=reason,
                        )
                    else:
                        # Failed without plan -> ready
                        resume_failed_issue_to_ready(
                            issue_number=issue_number,
                            repo=repo,
                            reason=reason,
                        )

                elif resume_kind == "blocked":
                    # Blocked -> ready
                    resume_blocked_issue_to_ready(
                        issue_number=issue_number,
                        repo=repo,
                        reason=reason,
                    )

                    # Clean up stale flow metadata
                    flow = candidate.get("flow")
                    if flow and hasattr(flow, "branch"):
                        self._cleanup_stale_flow(flow.branch)

                result["resumed"].append(
                    {"number": issue_number, "resume_kind": resume_kind}
                )

            except Exception:
                # Skip on error, could log here
                result["skipped"].append(
                    {"number": issue_number, "reason": "恢复操作失败"}
                )

        return result

    def _verify_issue_state_for_resume(
        self, issue_number: int, resume_kind: str, repo: str | None
    ) -> bool:
        """Verify issue is still in expected state for resume.

        Args:
            issue_number: GitHub issue number
            resume_kind: Expected resume kind ("failed" or "blocked")
            repo: Repository (owner/repo format, optional)

        Returns:
            True if issue state matches resume_kind, False otherwise
        """
        current_state = self.label_service.get_state(issue_number)

        if current_state is None:
            return False

        if resume_kind == "failed":
            return current_state.value == "failed"
        elif resume_kind == "blocked":
            return current_state.value == "blocked"

        return False

    def _cleanup_stale_flow(self, branch: str) -> None:
        """Clean up stale flow metadata after blocked resume.

        Args:
            branch: Branch name for the flow to clean up
        """
        try:
            logger.bind(
                domain="resume",
                action="cleanup_stale_flow",
                branch=branch,
            ).info("Cleaning up stale flow")

            # Reactivate the stale flow (change status from "stale" to "active")
            self.flow_service.reactivate_flow(branch)
        except Exception as exc:
            # Log but don't fail the resume operation
            logger.bind(
                domain="resume",
                action="cleanup_stale_flow",
                branch=branch,
            ).warning(f"Failed to clean up stale flow: {exc}")
