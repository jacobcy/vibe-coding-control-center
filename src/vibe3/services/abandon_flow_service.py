"""Abandon flow service - unified abandonment orchestration.

This service coordinates the full abandonment flow:
- Close GitHub issue
- Close open PR if present
- Mark flow as aborted
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models.orchestration import IssueState

if TYPE_CHECKING:
    from vibe3.services.flow_service import FlowService
    from vibe3.services.pr_service import PRService
    from vibe3.services.ready_close_service import ReadyCloseService


class AbandonFlowService:
    """Orchestrates complete flow abandonment.

    This service coordinates multiple operations for abandoning a flow:
    1. Close the GitHub issue via ReadyCloseService
    2. Close any open PR for the branch via PRService
    3. Mark the flow as aborted via FlowService

    The abandonment is atomic - if any step fails, the error is logged
    but the process continues to attempt remaining steps.
    """

    _ready_close: ReadyCloseService
    _pr_service: PRService
    _flow_service: FlowService

    def __init__(
        self,
        ready_close: ReadyCloseService | None = None,
        pr_service: PRService | None = None,
        flow_service: FlowService | None = None,
    ) -> None:
        """Initialize abandon flow service.

        Args:
            ready_close: Service for closing issues
            pr_service: Service for managing PRs
            flow_service: Service for flow lifecycle
        """
        # Lazy load if not provided
        if ready_close is None:
            from vibe3.clients.github_client import GitHubClient
            from vibe3.services.ready_close_service import ReadyCloseService

            ready_close = ReadyCloseService(github=GitHubClient())

        if pr_service is None:
            from vibe3.services.pr_service import PRService

            pr_service = PRService()

        if flow_service is None:
            from vibe3.services.flow_service import FlowService

            flow_service = FlowService()

        self._ready_close = ready_close
        self._pr_service = pr_service
        self._flow_service = flow_service

    def abandon_flow(
        self,
        issue_number: int,
        branch: str,
        source_state: IssueState,
        reason: str,
        actor: str = "agent:manager",
    ) -> dict[str, str | int | None]:
        """Execute complete flow abandonment.

        Args:
            issue_number: GitHub issue number
            branch: Branch name for the flow
            source_state: Current issue state (READY or HANDOFF)
            reason: Reason for abandonment
            actor: Actor performing the abandonment

        Returns:
            Dict with results for each step:
                - issue: "closed" or "failed"
                - pr: PR number if closed, None if no PR
                - flow: "aborted" or "failed"
        """
        logger.bind(
            domain="abandon",
            issue_number=issue_number,
            branch=branch,
            source_state=source_state.value,
            reason=reason,
        ).info("Starting flow abandonment")

        results: dict[str, str | int | None] = {}

        # Step 1: Close issue
        closing_comment = f"[manager] 任务放弃。\n\n原因:{reason}"
        try:
            results["issue"] = self._ready_close.close_ready_issue(
                issue_number, closing_comment=closing_comment
            )
        except Exception as e:
            logger.bind(
                domain="abandon",
                issue_number=issue_number,
            ).error(f"Failed to close issue: {e}")
            results["issue"] = "failed"

        # Step 2: Close PR if exists
        try:
            pr_comment = f"[manager] PR 放弃。\n\n原因:{reason}"
            closed_pr = self._pr_service.close_open_pr_for_flow(
                branch=branch, comment=pr_comment
            )
            results["pr"] = closed_pr  # PR number or None
        except Exception as e:
            logger.bind(
                domain="abandon",
                branch=branch,
            ).warning(f"Failed to close PR: {e}")
            results["pr"] = None

        # Step 3: Abort flow
        try:
            self._flow_service.abort_flow(branch=branch, reason=reason, actor=actor)
            results["flow"] = "aborted"
        except Exception as e:
            logger.bind(
                domain="abandon",
                branch=branch,
            ).error(f"Failed to abort flow: {e}")
            results["flow"] = "failed"

        logger.bind(
            domain="abandon",
            issue_number=issue_number,
            results=results,
        ).success("Flow abandonment completed")

        return results
