"""Check cleanup service - handles --clean-branch logic for terminal flows.

This service is separated from check_service.py to keep responsibilities clear:
- check_service.py: Consistency verification and auto-fix
- check_cleanup_service.py: Physical resource cleanup for terminal flows
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.services.flow_cleanup_service import FlowCleanupService


class LiveSessionQueryError(SystemError):
    """Raised when live session batch query fails, preventing unsafe cleanup."""


class CheckCleanupService:
    """Service for cleaning up terminal flow resources.

    Handles the --clean-branch functionality:
    - done: Clean physical resources, keep flow record as audit history
    - aborted: Clean everything including flow record (allows issue to restart)
    """

    # Terminal flow statuses that indicate completed flows.
    # "merged" was a historical status now migrated to "done" by
    # FlowState.migrate_flow_status in models/flow.py.
    TERMINAL_FLOW_STATUSES = ("done", "aborted")

    def __init__(
        self,
        store: "SQLiteClient",
        git_client: "GitClient",
        github_client: "GitHubClient | None" = None,
        session_registry: "SessionRegistryService | None" = None,
    ) -> None:
        self.store = store
        self.git_client = git_client
        self._github_client = github_client
        self._session_registry = session_registry

    @property
    def session_registry(self) -> "SessionRegistryService":
        """Lazy-initialized SessionRegistryService with default backend."""
        if self._session_registry is None:
            from vibe3.agents.backends.codeagent import CodeagentBackend
            from vibe3.environment.session_registry import SessionRegistryService

            backend = CodeagentBackend()
            self._session_registry = SessionRegistryService(
                store=self.store, backend=backend
            )
        return self._session_registry

    def clean_residual_branches(self) -> dict[str, object]:
        """Check and clean residual branches for terminal flows.

        Different handling based on flow status:
        - done: Clean physical resources, keep flow record as audit history
        - aborted: Clean everything including flow record (allows issue to restart)

        Returns:
            Dict with summary and details of cleaned branches.
        """
        from vibe3.services.flow_cleanup_service import FlowCleanupService

        logger.bind(domain="check", action="clean_residual").info(
            "Checking for residual branches"
        )

        # Get all terminal flows (done/aborted)
        all_flows = self.store.get_all_flows()
        terminal_flows = [
            f for f in all_flows if f.get("flow_status") in self.TERMINAL_FLOW_STATUSES
        ]

        # PRE-FILTER: Get branches with live sessions (batch query)
        # Fail-fast: if query fails, abort cleanup to prevent unsafe deletion
        try:
            branches_with_live = self._get_branches_with_live_sessions()
        except LiveSessionQueryError:
            raise  # Propagate to caller (CLI layer handles user-facing error)

        if branches_with_live:
            logger.bind(domain="check").info(
                f"Skipped {len(branches_with_live)} branches with live sessions: "
                f"{', '.join(sorted(branches_with_live))}"
            )

        cleanup_service = FlowCleanupService(
            git_client=self.git_client,
            store=self.store,
        )

        cleaned: list[str] = []
        kept_records: list[str] = []
        removed_invalid: list[str] = []
        failed: list[str] = []
        skipped_live: list[str] = []

        for flow in terminal_flows:
            branch = flow["branch"]
            flow_status = flow.get("flow_status", "")

            # Remove invalid branch records (e.g., HEAD)
            if self._is_invalid_branch_name(branch):
                if self._remove_invalid_flow_record(branch):
                    removed_invalid.append(branch)
                continue

            # SKIP: Branch has live sessions
            if branch in branches_with_live:
                skipped_live.append(branch)
                continue

            # Process valid terminal flow
            self._process_terminal_flow(
                branch=branch,
                flow_status=flow_status,
                cleanup_service=cleanup_service,
                cleaned=cleaned,
                kept_records=kept_records,
                failed=failed,
            )

        summary = f"Cleaned {len(cleaned)} aborted flows"
        if kept_records:
            summary += f", preserved {len(kept_records)} done records"
        if removed_invalid:
            summary += f", removed {len(removed_invalid)} invalid records"
        if skipped_live:
            summary += f", skipped {len(skipped_live)} branches with live sessions"
        if failed:
            summary += f", failed {len(failed)}"

        return {
            "summary": summary,
            "cleaned": cleaned,
            "kept_records": kept_records,
            "removed_invalid": removed_invalid,
            "failed": failed,
            "skipped_live": skipped_live,
            "total_flows_checked": len(terminal_flows),
        }

    def _get_branches_with_live_sessions(self) -> set[str]:
        """Batch query all live sessions and return branches with active sessions.

        This is a pre-filter optimization: instead of checking live sessions
        per branch during cleanup (N queries), we query once upfront and
        filter out branches with live sessions before cleanup attempts.

        Returns:
            Set of branch names that have truly live sessions.

        Raises:
            LiveSessionQueryError: If batch query fails, preventing
                unsafe cleanup. This fail-fast strategy ensures live
                session protection is never bypassed.
        """
        try:
            # Use injected or lazy-initialized SessionRegistryService
            return self.session_registry.get_all_branches_with_live_sessions()

        except Exception as exc:
            logger.bind(domain="check").error(
                f"Failed to query live sessions: {exc}. "
                "Cannot proceed with cleanup - "
                "live session protection must not be bypassed."
            )
            raise LiveSessionQueryError(
                f"Live session batch query failed: {exc}. "
                "Cleanup aborted to prevent accidental deletion of active sessions. "
                "Please verify manually or retry."
            ) from exc

    def _is_invalid_branch_name(self, branch: str) -> bool:
        """Check if branch name is invalid (e.g., HEAD, HEAD~1)."""
        return branch == "HEAD" or branch.startswith("HEAD")

    def _remove_invalid_flow_record(self, branch: str) -> bool:
        """Remove invalid flow record from database.

        Returns:
            True if successfully removed, False otherwise.
        """
        try:
            self.store.delete_flow(branch)
            logger.bind(domain="check", branch=branch).info(
                "Removed invalid flow record"
            )
            return True
        except Exception as exc:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to remove invalid flow record: {exc}"
            )
            return False

    def _process_terminal_flow(
        self,
        branch: str,
        flow_status: str,
        cleanup_service: "FlowCleanupService",
        cleaned: list[str],
        kept_records: list[str],
        failed: list[str],
    ) -> None:
        """Process a single terminal flow with appropriate cleanup.

        Args:
            branch: Branch name
            flow_status: Flow status (done/aborted)
            cleanup_service: Cleanup service instance
            cleaned: List to append successfully cleaned aborted flows
            kept_records: List to append done flows with preserved records
            failed: List to append failure messages
        """
        # done: keep record as audit history (issue is closed, PR was merged)
        # aborted: delete record (issue may still be open, allow restart)
        keep_flow_record = flow_status == "done"

        try:
            results = cleanup_service.cleanup_flow_scene(
                branch,
                include_remote=True,
                terminate_sessions=True,
                keep_flow_record=keep_flow_record,
            )

            if keep_flow_record:
                # done: success if physical resources cleaned
                if results.get("worktree", False) or results.get("local_branch", False):
                    kept_records.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        "Cleaned done flow resources, kept record"
                    )
            else:
                # aborted: success if flow record deleted
                if results.get("flow_record", False):
                    cleaned.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        "Cleaned aborted flow completely"
                    )

                    # Resume blocked issue to READY (passive cleanup)
                    self._resume_blocked_issue(branch)
                else:
                    failed.append(f"{branch}: flow record deletion failed")
        except Exception as exc:
            failed.append(f"{branch}: {exc}")
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to clean terminal flow resources: {exc}"
            )

    def _resume_blocked_issue(self, branch: str) -> None:
        """Resume blocked issue when flow is aborted (passive cleanup).

        This closes the cleanup loop for vibe check --clean-branch:
        when a flow is detected as aborted and cleaned up, the corresponding
        issue should return to READY state, allowing it to be dispatched again.

        Skips already-closed issues to avoid reopening completed work.

        Args:
            branch: Branch name (expected to be task/issue-N pattern)
        """
        try:
            from vibe3.models.orchestration import IssueState
            from vibe3.services.issue_failure_service import resume_issue

            issue_number = self._parse_issue_number(branch)
            if issue_number is None:
                logger.bind(domain="check", branch=branch).debug(
                    "Not a task branch, skipping issue label cleanup"
                )
                return

            from vibe3.clients.github_client import GitHubClient

            gh = self._github_client or GitHubClient()
            gh_issue = gh.view_issue(issue_number)
            if (
                isinstance(gh_issue, dict)
                and str(gh_issue.get("state", "")).upper() == "CLOSED"
            ):
                logger.bind(domain="check", branch=branch).info(
                    f"Issue #{issue_number} already closed, skip resume"
                )
                return

            current_state = self._get_issue_state(issue_number)
            from_state = current_state if current_state else "blocked"

            resume_issue(
                issue_number=issue_number,
                reason="Flow aborted and cleaned up by vibe check --clean-branch",
                from_state=from_state,
                to_state=IssueState.READY,
            )

            logger.bind(domain="check", branch=branch).info(
                f"Resumed issue #{issue_number} to READY (from {from_state})"
            )
        except Exception as exc:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to resume blocked issue: {exc}"
            )

    def _get_issue_state(self, issue_number: int) -> str | None:
        """Get current issue state for event record.

        Args:
            issue_number: GitHub issue number

        Returns:
            Current state value (e.g., "blocked", "ready") or None if unknown
        """
        try:
            from vibe3.services.label_service import LabelService

            state = LabelService().get_state(issue_number)
            return state.value if state else None
        except Exception as exc:
            logger.bind(
                domain="check",
                issue_number=issue_number,
            ).debug(f"Failed to get issue state: {exc}")
            return None

    def _parse_issue_number(self, branch: str) -> int | None:
        """Extract issue number from task/issue-N branch."""
        import re

        match = re.fullmatch(r"^task/issue-(\d+)$", branch)
        return int(match.group(1)) if match else None
