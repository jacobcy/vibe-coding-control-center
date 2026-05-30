"""Check PR service - handles PR state changes during consistency checks.

This service is separated from check_service.py to keep responsibilities clear:
- check_service.py: Core consistency verification and branch checking
- check_pr_service.py: PR state change detection and handling
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.models.pr import PRState

if TYPE_CHECKING:
    from vibe3.clients import GitClient, GitHubClient, SQLiteClient
    from vibe3.models.pr import PRResponse
    from vibe3.services.flow_status_service import FlowStatusService


class CheckPRService:
    """Service for handling PR state changes during consistency checks.

    Responsibilities:
    - Detect PR merged/closed status changes
    - Handle merged PR: mark flow done, auto-close linked issues
    - Handle closed PR: reset issue to READY, clean up flow scene
    - Update PR cache when state changes detected
    """

    def __init__(
        self,
        store: "SQLiteClient",
        git_client: "GitClient",
        github_client: "GitHubClient",
        flow_status_service: "FlowStatusService",
    ) -> None:
        self.store = store
        self.git_client = git_client
        self.github_client = github_client
        self._flow_status_service = flow_status_service

    def _already_handled_pr_closed(self, branch: str, pr: "PRResponse") -> bool:
        """Check if PR closed event was already handled.

        Idempotency guard to prevent duplicate handling on periodic checks.

        Args:
            branch: Branch name
            pr: PR response object

        Returns:
            True if already handled (should skip), False if should handle
        """
        flow_state = self.store.get_flow_state(branch)
        if not flow_state:
            return False

        initiated_by = str(flow_state.get("initiated_by") or "")
        if initiated_by != "check:pr_closed":
            return False

        if pr.closed_at is None:
            # No closed_at available — assume already handled to avoid flooding
            return True

        # Normalize both timestamps to UTC-aware datetime for accurate comparison
        from datetime import datetime, timezone

        flow_updated_str = str(flow_state.get("updated_at") or "")
        if not flow_updated_str:
            return False

        try:
            # Parse flow_updated (local time without timezone, assume UTC)
            flow_updated = datetime.fromisoformat(flow_updated_str)
            if flow_updated.tzinfo is None:
                flow_updated = flow_updated.replace(tzinfo=timezone.utc)

            # pr.closed_at is already a datetime, ensure UTC
            pr_closed_at = pr.closed_at
            if pr_closed_at.tzinfo is None:
                pr_closed_at = pr_closed_at.replace(tzinfo=timezone.utc)

            return flow_updated >= pr_closed_at
        except (ValueError, TypeError):
            # Fallback to string comparison if datetime parsing fails
            logger.bind(
                domain="check",
                action="idempotency_guard",
                branch=branch,
            ).warning("Failed to parse timestamps, falling back to string comparison")
            return flow_updated_str >= pr.closed_at.isoformat()

    def _abort_and_cleanup(
        self,
        branch: str,
        reason: str,
        extra_warning_suffix: str = "",
    ) -> tuple[None, list[str]]:
        """Mark flow as aborted and clean up physical resources.

        Args:
            branch: Branch name
            reason: Reason for abort (e.g., "issue #123 already closed")
            extra_warning_suffix: Optional suffix for warning message

        Returns:
            Tuple of (None, warning_messages)
        """
        self._flow_status_service.mark_flow_aborted(branch, reason)

        # Clean up physical resources (worktree, branches, flow record)
        from vibe3.services.flow_cleanup_service import (
            FlowCleanupService,
            LiveSessionsDetectedError,
        )

        cleanup_service = FlowCleanupService(
            store=self.store,
            git_client=self.git_client,
        )

        try:
            cleanup_result = cleanup_service.cleanup_flow_scene(
                branch, include_remote=True, keep_flow_record=False
            )

            # Build warning message from cleanup results
            cleaned_items = []
            if cleanup_result.get("worktree") is True:
                cleaned_items.append("worktree")
            if cleanup_result.get("local_branch") is True:
                cleaned_items.append("local branch")
            if cleanup_result.get("remote_branch") is True:
                cleaned_items.append("remote branch")
            if cleanup_result.get("flow_record") is True:
                cleaned_items.append("flow record")

            warning_msg = (
                f"Flow '{branch}' marked aborted ({reason}); "
                f"cleaned: {', '.join(cleaned_items)}"
                if cleaned_items
                else f"Flow '{branch}' marked aborted ({reason}, no cleanup needed)"
            )
            if extra_warning_suffix:
                warning_msg += f"; {extra_warning_suffix}"
            return (None, [warning_msg])

        except LiveSessionsDetectedError as exc:
            warning_msg = (
                f"Flow '{branch}' marked aborted ({reason}); " f"cleanup skipped: {exc}"
            )
            logger.bind(
                domain="check",
                action="reset_pr_closed",
                branch=branch,
            ).warning(warning_msg)
            return (None, [warning_msg])

    def handle_closed_pr(
        self,
        branch: str,
        pr: "PRResponse",
    ) -> tuple[bool, list[str], list[str]]:
        """Handle PR state changes detected during check.

        Args:
            branch: Branch name
            pr: PR response object

        Returns:
            Tuple of (handled, issues, warnings).
            - handled: True if PR was merged or closed (caller should return early)
            - issues: List of error/issue messages
            - warnings: List of warning messages
        """
        if pr.merged_at or pr.state == PRState.MERGED:
            return self._handle_merged_pr(branch, pr)

        if pr.state == PRState.CLOSED:
            if self._already_handled_pr_closed(branch, pr):
                return (False, [], [])
            return self._handle_closed_pr(branch, pr)

        # PR still open, nothing to handle
        return (False, [], [])

    def _handle_merged_pr(
        self, branch: str, pr: "PRResponse"
    ) -> tuple[bool, list[str], list[str]]:
        """Handle merged PR: mark flow done, auto-close linked issues.

        Returns:
            Tuple of (handled=True, issues, warnings).
        """
        warnings: list[str] = []

        suggestions = self._flow_status_service.mark_flow_done(
            branch,
            f"PR #{pr.number} merged (detected from GitHub)",
        )
        self._update_pr_cache(branch, pr)

        if suggestions.get("issue_to_close"):
            # Informational message, not an error
            warnings.append(
                f"Issue #{suggestions['issue_to_close']} was still OPEN — "
                "auto-closed because PR was merged."
            )

        return (True, [], warnings)

    def _handle_closed_pr(
        self, branch: str, pr: "PRResponse"
    ) -> tuple[bool, list[str], list[str]]:
        """Handle closed PR (without merge): reset issue, clean up.

        Returns:
            Tuple of (handled=True, issues, warnings).
        """
        reset_error, reset_warnings = self._reset_issue_after_pr_closed(
            branch, pr.number
        )
        self._update_pr_cache(branch, pr)

        if reset_error:
            return (True, [reset_error], [])

        return (True, [], reset_warnings)

    def _reset_issue_after_pr_closed(
        self, branch: str, pr_number: int
    ) -> tuple[str | None, list[str]]:
        """Reset issue to READY after PR closed without merge.

        Cleans up flow scene (worktree, branch, flow record) and
        restores issue to READY state so it can be dispatched again.

        Args:
            branch: Branch name (e.g., "task/issue-456")
            pr_number: Closed PR number

        Returns:
            Tuple of (error_str, warnings). error_str is None on success,
            warnings contains cleanup result messages.
        """
        from vibe3.models.flow import FlowStatusResponse
        from vibe3.services.task_resume_operations import TaskResumeOperations

        # Find task issue number
        issue_links = self.store.get_issue_links(branch)
        task_issue_number: int | None = None
        for link in issue_links:
            if link.get("issue_role") == "task":
                task_issue_number = link.get("issue_number")
                if isinstance(task_issue_number, int):
                    break

        if not task_issue_number:
            logger.bind(
                domain="check",
                action="reset_pr_closed",
                branch=branch,
            ).debug("No task issue linked, marking flow as aborted instead")
            # No issue link → just mark flow as aborted (PR abandoned)
            return self._abort_and_cleanup(
                branch,
                f"PR #{pr_number} closed without merge (no issue link)",
            )

        # Check if issue already closed
        gh_issue = self.github_client.view_issue(task_issue_number)
        if isinstance(gh_issue, dict):
            issue_state = str(gh_issue.get("state", "")).upper()
            if issue_state == "CLOSED":
                logger.bind(
                    domain="check",
                    action="reset_pr_closed",
                    branch=branch,
                    issue_number=task_issue_number,
                ).info(
                    f"Issue #{task_issue_number} already closed, "
                    "marking flow as aborted"
                )

                # Issue already closed → mark flow as aborted and clean up
                return self._abort_and_cleanup(
                    branch,
                    f"Issue #{task_issue_number} already closed; "
                    f"PR #{pr_number} closed without merge",
                )

        # Build minimal FlowStatusResponse for task resume
        flow = FlowStatusResponse(
            branch=branch,
            flow_slug=branch,
            flow_status="active",
            latest_actor="vibe:check",
            task_issue_number=task_issue_number,
        )

        # Create TaskResumeOperations and reset to READY
        from vibe3.services.flow_service import FlowService
        from vibe3.services.issue_flow_service import IssueFlowService
        from vibe3.services.label_service import LabelService

        label_service = LabelService()
        flow_service = FlowService(store=self.store)
        issue_flow_service = IssueFlowService(store=self.store)

        resume_ops = TaskResumeOperations(
            git_client=self.git_client,
            github_client=self.github_client,
            flow_service=flow_service,
            label_service=label_service,
            issue_flow_service=issue_flow_service,
        )

        try:
            resume_ops.reset_issue_to_ready(
                issue_number=task_issue_number,
                resume_kind="pr_closed",
                flow=flow,
                repo=None,
                reason=f"PR #{pr_number} closed without merge, resetting to READY",
            )

            logger.bind(
                domain="check",
                action="reset_pr_closed",
                branch=branch,
                issue_number=task_issue_number,
            ).info(
                f"Reset issue #{task_issue_number} to READY after "
                f"PR #{pr_number} closed"
            )

            # Rebuild flow after reset to avoid dangling state
            from vibe3.config.orchestra_config import OrchestraConfig
            from vibe3.services.flow_orchestrator_service import (
                FlowOrchestratorService,
            )
            from vibe3.services.issue_context_loader import load_issue_info

            config = OrchestraConfig()
            orchestrator = FlowOrchestratorService(
                config,
                store=self.store,
                git=self.git_client,
                github=self.github_client,
            )

            issue_info = load_issue_info(
                task_issue_number, config=config, github=self.github_client
            )

            # Create new flow (ensure_worktree=False to delay creation)
            orchestrator.bootstrap_issue_flow(
                issue_info,
                branch=branch,
                slug=f"issue-{task_issue_number}",
                source="check:pr_closed",
                initiated_by="check:pr_closed",
                ensure_worktree=False,
                reactivate_existing=False,
            )

            logger.bind(
                domain="check",
                action="reset_pr_closed_rebuild",
                branch=branch,
                issue_number=task_issue_number,
            ).info(
                f"Rebuilt flow for issue #{task_issue_number} after "
                f"PR #{pr_number} closed"
            )

            # Record handoff milestone (optional but recommended)
            from vibe3.services.handoff_service import HandoffService

            handoff_service = HandoffService(
                store=self.store,
                git_client=self.git_client,
                github_client=self.github_client,
            )

            handoff_service.append_current_handoff(
                message=(
                    f"PR #{pr_number} closed without merge, "
                    f"flow rebuilt and reset to READY"
                ),
                actor="vibe:check",
                kind="milestone",
                branch=branch,
            )

        except Exception as exc:
            logger.bind(
                domain="check",
                action="reset_pr_closed",
                branch=branch,
                issue_number=task_issue_number,
            ).warning(f"Failed to reset issue: {exc}")
            return (
                f"Failed to reset issue #{task_issue_number} after PR "
                f"#{pr_number} closed: {exc}",
                [],
            )

        return (None, [])

    def _update_pr_cache(self, branch: str, pr: "PRResponse") -> None:
        """Update PR cache when check discovers changes.

        This is a write operation: check command updates cache
        when it discovers PR state changes.

        Args:
            branch: Branch name
            pr: PR response object with title and number
        """
        try:
            from vibe3.services.issue_title_cache_service import IssueTitleCacheService

            title_cache = IssueTitleCacheService(self.store, self.github_client)
            title_cache.update_pr(
                branch=branch,
                pr_number=pr.number,
                pr_title=pr.title,
            )
            logger.bind(domain="check", branch=branch).info(
                f"Updated PR cache: #{pr.number} - {pr.title}"
            )
        except Exception as e:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to update PR cache: {e}"
            )
