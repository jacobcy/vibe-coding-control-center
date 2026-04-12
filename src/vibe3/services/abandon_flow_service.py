"""Abandon flow service - unified abandonment orchestration.

This service coordinates the full abandonment flow:
- Close GitHub issue
- Close open PR if present
- Mark flow as aborted
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState

if TYPE_CHECKING:
    from vibe3.services.flow_service import FlowService
    from vibe3.services.pr_service import PRService


class AbandonFlowService:
    """Orchestrates complete flow abandonment.

    This service coordinates multiple operations for abandoning a flow:
    1. Close the GitHub issue via GitHubClient
    2. Close any open PR for the branch via PRService
    3. Mark the flow as aborted via FlowService

    The abandonment is atomic - if any step fails, the error is logged
    but the process continues to attempt remaining steps.
    """

    _github: GitHubClient
    _pr_service: PRService
    _flow_service: FlowService

    def __init__(
        self,
        github: GitHubClient | None = None,
        pr_service: PRService | None = None,
        flow_service: FlowService | None = None,
    ) -> None:
        """Initialize abandon flow service.

        Args:
            github: GitHub client for issue operations
            pr_service: Service for managing PRs
            flow_service: Service for flow lifecycle
        """
        if github is None:
            github = GitHubClient()

        if pr_service is None:
            from vibe3.services.pr_service import PRService

            pr_service = PRService()

        if flow_service is None:
            from vibe3.services.flow_service import FlowService

            flow_service = FlowService()

        self._github = github
        self._pr_service = pr_service
        self._flow_service = flow_service

    def abandon_flow(
        self,
        issue_number: int,
        branch: str,
        source_state: IssueState,
        reason: str,
        actor: str = "agent:manager",
        issue_already_closed: bool = False,
        flow_already_aborted: bool = False,
    ) -> dict[str, str | int | None]:
        """Execute complete flow abandonment.

        Args:
            issue_number: GitHub issue number
            branch: Branch name for the flow
            source_state: Current issue state (READY or HANDOFF)
            reason: Reason for abandonment
            actor: Actor performing the abandonment
            issue_already_closed: If True, skip the issue close API call
            flow_already_aborted: If True, skip writing another abort event

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
        if issue_already_closed:
            results["issue"] = "closed"
        else:
            try:
                results["issue"] = self._github.close_issue_if_open(
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
        if flow_already_aborted:
            results["flow"] = "aborted"
        else:
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
