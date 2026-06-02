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
    from vibe3.clients import SQLiteClient
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
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

    def _find_existing_bridge_marker(
        self, issue_number: int, closed_pr_number: int
    ) -> int | None:
        """Check if a bridge marker already exists for this PR.

        Args:
            issue_number: Original issue number
            closed_pr_number: Closed PR number

        Returns:
            Successor bridge issue number if marker found, None otherwise.
        """
        import re

        try:
            comments = self.github_client.list_issue_comments(issue_number)
            if not comments:
                return None

            # Look for bridge marker comment
            # Check for both the marker header and the specific closed_pr reference
            for comment in comments:
                if not isinstance(comment, dict):
                    continue
                body = comment.get("body", "")
                # Check if this is a bridge marker for this specific PR
                if (
                    "[flow] Bridge issue created" in body
                    and f"closed_pr: #{closed_pr_number}" in body
                ):
                    successor_match = re.search(r"^successor:\s*#(\d+)\s*$", body, re.M)
                    if not successor_match:
                        logger.bind(
                            domain="check",
                            action="bridge_idempotency",
                            issue_number=issue_number,
                            closed_pr=closed_pr_number,
                        ).warning("Found bridge marker without successor issue number")
                        return None

                    bridge_number = int(successor_match.group(1))
                    logger.bind(
                        domain="check",
                        action="bridge_idempotency",
                        issue_number=issue_number,
                        closed_pr=closed_pr_number,
                        bridge_issue=bridge_number,
                    ).debug("Found existing bridge marker, skipping creation")
                    return bridge_number

            return None

        except Exception as exc:
            logger.bind(
                domain="check",
                action="bridge_idempotency",
                issue_number=issue_number,
            ).warning(f"Failed to check for existing bridge marker: {exc}")
            return None

    def _inherit_labels_for_bridge(
        self, original_issue: dict, closed_pr_number: int
    ) -> list[str]:
        """Prepare labels for bridge issue.

        Inherit classification labels from original issue, exclude state labels,
        and add state/ready.

        Args:
            original_issue: Original issue payload from view_issue()
            closed_pr_number: Closed PR number (for logging)

        Returns:
            List of labels to apply to bridge issue
        """
        # Get labels from original issue
        original_labels = original_issue.get("labels", [])
        inherited = []

        for label_data in original_labels:
            label_name = label_data.get("name", "")
            # Exclude state/* labels and vibe-task
            if label_name.startswith("state/"):
                continue
            if label_name == "vibe-task":
                continue
            inherited.append(label_name)

        # Add state/ready
        if "state/ready" not in inherited:
            inherited.append("state/ready")

        logger.bind(
            domain="check",
            action="bridge_labels",
            original_labels=[label.get("name") for label in original_labels],
            inherited_labels=inherited,
        ).debug("Prepared labels for bridge issue")

        return inherited

    def _create_bridge_issue(
        self,
        original_issue_number: int,
        original_issue: dict,
        closed_pr_number: int,
        branch: str,
    ) -> int | None:
        """Create a bridge issue for abandoned work.

        Args:
            original_issue_number: Original issue number
            original_issue: Original issue payload
            closed_pr_number: Closed PR number
            branch: Branch name

        Returns:
            Bridge issue number on success, None on failure
        """
        # Prepare title
        original_title = original_issue.get("title", "Unknown Issue")
        bridge_title = f"Follow-up: {original_title}"

        # Prepare body
        original_body = original_issue.get("body", "")
        bridge_body = f"""[flow] Bridge issue

status: unresolved
source_issue: #{original_issue_number}
closed_pr: #{closed_pr_number}
source_branch: {branch}
reason: linked PR closed without merge; health check closed the old execution lineage

## Context

The original issue remains unresolved, but its previous PR was closed without merge.
This bridge issue is the new execution target.

## Original Issue

{original_body}

## Contributors

- @jacobcy
- Codex
"""

        # Prepare labels
        labels = self._inherit_labels_for_bridge(original_issue, closed_pr_number)

        # Create bridge issue
        bridge_number = self.github_client.create_issue(
            title=bridge_title,
            body=bridge_body,
            labels=labels,
        )

        if bridge_number:
            logger.bind(
                domain="check",
                action="bridge_created",
                bridge_issue=bridge_number,
                original_issue=original_issue_number,
                closed_pr=closed_pr_number,
            ).info(
                f"Created bridge issue #{bridge_number} for "
                f"original #{original_issue_number} after PR #{closed_pr_number} closed"
            )

        return bridge_number

    def _add_bridge_marker_to_original(
        self,
        original_issue_number: int,
        bridge_issue_number: int,
        closed_pr_number: int,
        branch: str,
    ) -> bool:
        """Add bridge marker comment to original issue.

        Args:
            original_issue_number: Original issue number
            bridge_issue_number: Bridge issue number
            closed_pr_number: Closed PR number
            branch: Branch name

        Returns:
            True on success, False on failure
        """
        marker_body = f"""[flow] Bridge issue created

successor: #{bridge_issue_number}
closed_pr: #{closed_pr_number}
source_branch: {branch}
status: unresolved_continues_in_successor
"""

        success = self.github_client.add_comment(original_issue_number, marker_body)

        if success:
            logger.bind(
                domain="check",
                action="bridge_marker_added",
                original_issue=original_issue_number,
                bridge_issue=bridge_issue_number,
            ).debug("Added bridge marker to original issue")
        else:
            logger.bind(
                domain="check",
                action="bridge_marker_failed",
                original_issue=original_issue_number,
            ).warning("Failed to add bridge marker to original issue")

        return success

    def _close_original_issue_with_comment(
        self,
        original_issue_number: int,
        bridge_issue_number: int,
        closed_pr_number: int,
    ) -> str:
        """Close original issue with explanatory comment.

        Args:
            original_issue_number: Original issue number
            bridge_issue_number: Bridge issue number
            closed_pr_number: Closed PR number

        Returns:
            Result string: "closed", "already_closed", or "failed"
        """
        closing_comment = f"""[flow] Closed after PR abandoned

PR #{closed_pr_number} was closed without merge, so this execution lineage is ended.
The unresolved work continues in #{bridge_issue_number}.
"""

        result = self.github_client.close_issue_if_open(
            issue_number=original_issue_number,
            closing_comment=closing_comment,
        )

        logger.bind(
            domain="check",
            action="original_closed",
            original_issue=original_issue_number,
            bridge_issue=bridge_issue_number,
            result=result,
        ).debug("Closed original issue after bridge creation")

        return result

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
        if not isinstance(gh_issue, dict):
            # Failed to fetch issue data (network error or not found)
            logger.bind(
                domain="check",
                action="reset_pr_closed",
                branch=branch,
                issue_number=task_issue_number,
            ).warning(
                f"Failed to fetch issue #{task_issue_number} data, "
                "preserving flow for retry"
            )
            # Do NOT cleanup flow - allow retry when GitHub API recovers
            return (
                f"Failed to fetch issue #{task_issue_number} data "
                f"(network/auth error), please retry later",
                [],
            )

        issue_state = str(gh_issue.get("state", "")).upper()
        if issue_state == "CLOSED":
            logger.bind(
                domain="check",
                action="reset_pr_closed",
                branch=branch,
                issue_number=task_issue_number,
            ).info(
                f"Issue #{task_issue_number} already closed, " "marking flow as aborted"
            )

            # Issue already closed → mark flow as aborted and clean up
            return self._abort_and_cleanup(
                branch,
                f"Issue #{task_issue_number} already closed; "
                f"PR #{pr_number} closed without merge",
            )

        # Check for existing bridge marker (idempotency)
        existing_bridge_number = self._find_existing_bridge_marker(
            task_issue_number, pr_number
        )
        if existing_bridge_number:
            close_result = self._close_original_issue_with_comment(
                original_issue_number=task_issue_number,
                bridge_issue_number=existing_bridge_number,
                closed_pr_number=pr_number,
            )
            if close_result == "failed":
                logger.bind(
                    domain="check",
                    action="reset_pr_closed",
                    branch=branch,
                    issue_number=task_issue_number,
                    bridge_issue=existing_bridge_number,
                ).warning(
                    f"Failed to close original issue #{task_issue_number} "
                    "after finding existing bridge marker, preserving flow for retry"
                )
                return (
                    f"Bridge issue #{existing_bridge_number} already exists, but "
                    f"failed to close original issue #{task_issue_number} "
                    "(network/permission error); please retry later or manually close",
                    [],
                )

            # Bridge already exists and original issue is closed, just abort and cleanup
            return self._abort_and_cleanup(
                branch,
                f"Bridge issue #{existing_bridge_number} already exists for "
                f"PR #{pr_number}; original issue #{task_issue_number} closed",
            )

        # Create bridge issue
        bridge_number = self._create_bridge_issue(
            original_issue_number=task_issue_number,
            original_issue=gh_issue,
            closed_pr_number=pr_number,
            branch=branch,
        )

        if not bridge_number:
            return (
                f"Failed to create bridge issue for #{task_issue_number} "
                f"after PR #{pr_number} closed",
                [],
            )

        # Add bridge marker to original issue
        self._add_bridge_marker_to_original(
            original_issue_number=task_issue_number,
            bridge_issue_number=bridge_number,
            closed_pr_number=pr_number,
            branch=branch,
        )

        # Close original issue
        close_result = self._close_original_issue_with_comment(
            original_issue_number=task_issue_number,
            bridge_issue_number=bridge_number,
            closed_pr_number=pr_number,
        )

        # Check if close succeeded
        if close_result == "failed":
            logger.bind(
                domain="check",
                action="reset_pr_closed",
                branch=branch,
                issue_number=task_issue_number,
                bridge_issue=bridge_number,
            ).warning(
                f"Failed to close original issue #{task_issue_number}, "
                f"preserving flow for retry"
            )
            # Do NOT cleanup flow - allow manual retry or intervention
            return (
                f"Failed to close original issue #{task_issue_number} "
                f"(network/permission error), bridge #{bridge_number} created; "
                f"please retry later or manually close",
                [],
            )

        # Abort and cleanup old flow
        return self._abort_and_cleanup(
            branch,
            f"Bridge issue #{bridge_number} created; "
            f"original #{task_issue_number} closed after PR #{pr_number} abandoned",
        )

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
