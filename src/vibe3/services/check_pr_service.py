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
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
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
            self._flow_status_service.mark_flow_aborted(
                branch, f"PR #{pr_number} closed without merge (no issue link)"
            )

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
                # Only report items that were actually cleaned (True means removed)
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
                    f"Flow '{branch}' marked aborted; "
                    f"cleaned: {', '.join(cleaned_items)}"
                    if cleaned_items
                    else f"Flow '{branch}' marked aborted (no cleanup needed)"
                )
                return (None, [warning_msg])

            except LiveSessionsDetectedError as exc:
                # Live sessions detected - skip cleanup but continue
                warning_msg = f"Flow '{branch}' marked aborted; cleanup skipped: {exc}"
                logger.bind(
                    domain="check",
                    action="reset_pr_closed",
                    branch=branch,
                ).warning(warning_msg)
                return (None, [warning_msg])

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
                ).info(f"Issue #{task_issue_number} already closed, skip reset")
                return (None, [])

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
