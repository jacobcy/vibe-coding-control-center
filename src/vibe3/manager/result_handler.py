"""Dispatch result handler for Orchestra manager.

Handles post-execution state and feedback.
"""

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models.orchestration import IssueState

if TYPE_CHECKING:
    from vibe3.manager.flow_manager import FlowManager
    from vibe3.models.orchestration import IssueInfo
    from vibe3.orchestra.config import OrchestraConfig


class DispatchResultHandler:
    """Handles side effects of dispatch execution (labels, comments, events)."""

    def __init__(
        self,
        config: "OrchestraConfig",
        flow_manager: "FlowManager",
    ):
        self.config = config
        self.flow_manager = flow_manager

    def update_state_label(self, issue_number: int, state: IssueState) -> None:
        """Update issue state label (display only, does not drive logic)."""
        try:
            from vibe3.services.label_service import LabelService

            LabelService(repo=self.config.repo).confirm_issue_state(
                issue_number,
                state,
                actor="orchestra:manager",
                force=True,
            )
        except Exception as e:
            logger.bind(domain="orchestra").warning(
                f"Failed to update label for #{issue_number}: {e}"
            )

    def on_dispatch_success(self, issue: "IssueInfo", flow_branch: str) -> None:
        """Handle successful dispatch: check PR and update state to review.

        Args:
            issue: Issue that was dispatched
            flow_branch: Flow branch name
        """
        log = logger.bind(
            domain="orchestra",
            action="dispatch_success",
            issue=issue.number,
        )

        # Check if PR exists
        pr_number = self.flow_manager.get_pr_for_issue(issue.number)
        if pr_number:
            # Update state to review
            self.update_state_label(issue.number, IssueState.REVIEW)
            log.info(
                f"Dispatch success, PR #{pr_number} exists, "
                f"advancing to state/review"
            )

            # Record event in flow history
            self.record_dispatch_event(
                flow_branch,
                success=True,
                issue_number=issue.number,
                pr_number=pr_number,
            )
        else:
            # No PR yet, keep in-progress state
            log.info("Dispatch success, no PR yet, keeping state/in-progress")

            # Record event in flow history
            self.record_dispatch_event(
                flow_branch,
                success=True,
                issue_number=issue.number,
                pr_number=None,
            )

    def on_dispatch_failure(self, issue: "IssueInfo", category: str) -> None:
        """Handle dispatch failure: update state and post comment.

        Args:
            issue: Issue that failed to dispatch
            category: Error category (api_error, timeout, business_error, etc.)
        """
        log = logger.bind(
            domain="orchestra",
            action="dispatch_failure",
            issue=issue.number,
            category=category,
        )

        # System/launch errors should fail the issue, not block it.
        if category in ("api_error", "timeout", "circuit_breaker"):
            self.update_state_label(issue.number, IssueState.FAILED)
            reason = (
                f"Orchestra dispatch 报错（{category}），"
                "已切换为 state/failed，等待修复"
            )
            self.post_failure_comment(issue.number, reason)
            log.warning(f"Issue failed due to {category}")

            # Record event in flow history
            flow = self.flow_manager.get_flow_for_issue(issue.number)
            if flow and flow.get("branch"):
                self.record_dispatch_event(
                    flow["branch"],
                    success=False,
                    issue_number=issue.number,
                    category=category,
                    reason=reason,
                )
            else:
                log.warning(
                    f"Cannot record dispatch event: no flow branch for #{issue.number}"
                )
        else:
            # Business error - keep in-progress, don't auto-block
            log.warning("Business error, keeping state/in-progress")

            # Record event in flow history
            flow = self.flow_manager.get_flow_for_issue(issue.number)
            if flow and flow.get("branch"):
                self.record_dispatch_event(
                    flow["branch"],
                    success=False,
                    issue_number=issue.number,
                    category=category,
                    reason="Business logic error, manual intervention may be needed",
                )
            else:
                log.warning(
                    f"Cannot record dispatch event: no flow branch for #{issue.number}"
                )

    def post_failure_comment(self, issue_number: int, reason: str) -> None:
        """Post failure comment on issue.

        Args:
            issue_number: Issue number
            reason: Failure reason
        """
        try:
            from vibe3.clients.github_client import GitHubClient

            GitHubClient().add_comment(
                issue_number,
                f"[Orchestra] {reason}",
                repo=self.config.repo,
            )
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to post failure comment for #{issue_number}: {exc}"
            )

    def record_dispatch_event(
        self,
        flow_branch: str,
        success: bool,
        issue_number: int,
        pr_number: int | None = None,
        category: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Record dispatch result as flow event for traceability.

        Args:
            flow_branch: Flow branch name
            success: Whether dispatch succeeded
            issue_number: Issue number
            pr_number: PR number (if exists)
            category: Error category (if failed)
            reason: Failure reason (if failed)
        """
        try:
            from vibe3.clients import SQLiteClient

            store = SQLiteClient()
            event_data: dict[str, int | str | bool | None] = {
                "success": success,
                "issue": issue_number,
            }
            if pr_number is not None:
                event_data["pr"] = pr_number
            if category is not None:
                event_data["category"] = category
            if reason is not None:
                event_data["reason"] = reason

            store.add_event(
                branch=flow_branch,
                event_type="dispatch_result",
                actor="orchestra:manager",
                detail="success" if success else f"failed:{category}",
                refs=event_data,
            )
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to record dispatch event for #{issue_number}: {exc}"
            )
