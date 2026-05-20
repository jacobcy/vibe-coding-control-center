"""Check cleanup service - handles --clean-branch logic for terminal flows.

This service is separated from check_service.py to keep responsibilities clear:
- check_service.py: Consistency verification and auto-fix
- check_cleanup_service.py: Physical resource cleanup for terminal flows
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.git_worktree_ops import remove_worktree

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow_cleanup_service import FlowCleanupService


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
    ) -> None:
        self.store = store
        self.git_client = git_client
        self._github_client = github_client

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
        branches_with_live = self._get_branches_with_live_sessions()

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
            SystemError: If query fails, preventing accidental cleanup.
        """
        try:
            from vibe3.agents.backends.codeagent import CodeagentBackend
            from vibe3.environment.session_registry import SessionRegistryService

            backend = CodeagentBackend()
            registry = SessionRegistryService(store=self.store, backend=backend)

            # Reuse existing method: batch query + liveness verification
            return registry.get_all_branches_with_live_sessions()

        except Exception as exc:
            logger.bind(domain="check").error(
                f"Failed to query live sessions: {exc}. "
                "Cannot proceed with cleanup - manual verification required."
            )
            raise SystemError(
                f"Live session query failed: {exc}. "
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

        SAFETY CHECK: Two-layer protection against live session deletion.
        - Layer 1 (pre-filter): Batch query upfront for performance optimization
        - Layer 2 (defensive): Per-branch verification in cleanup_flow_scene()
          (LiveSessionsDetectedError catches race conditions)
        If sessions are still running, cleanup aborted by LiveSessionsDetectedError.

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

    def _get_agent_worktree_base(self) -> Path:
        """Get agent worktree base directory (.claude/worktrees/)."""
        return Path(".claude/worktrees")

    def _clean_expired_agent_worktrees(
        self, max_age_days: int = 7
    ) -> dict[str, object]:
        """Clean expired agent worktrees older than max_age_days.

        Safety checks:
        - Check if worktree path has live runtime sessions
        - Skip worktrees with active sessions to avoid disrupting running agents

        Uses git worktree remove (not just rmtree) to properly clean both
        the physical directory and the git worktree metadata.

        Args:
            max_age_days: Max age in days before cleanup (default: 7)

        Returns:
            Dict with 'cleaned' list and 'skipped_live' list
        """
        from datetime import datetime, timedelta

        logger.bind(domain="check", action="clean_agent_worktrees").info(
            f"Checking agent worktrees older than {max_age_days} days"
        )

        base = self._get_agent_worktree_base()
        if not base.exists():
            return {"cleaned": [], "skipped_live": [], "failed": []}

        cutoff = datetime.now() - timedelta(days=max_age_days)

        cleaned: list[str] = []
        skipped_live: list[str] = []
        failed: list[str] = []

        # Scan agent-* worktrees
        for worktree_dir in base.glob("agent-*"):
            if not worktree_dir.is_dir():
                continue

            worktree_name = worktree_dir.name

            try:
                # Get last modified time
                mtime = datetime.fromtimestamp(worktree_dir.stat().st_mtime)

                # Check age
                if mtime >= cutoff:
                    continue

                # Check if worktree path has live runtime sessions.
                # Uses absolute path to match worktree_path stored in
                # runtime_session table (populated by vibe3 worktree creation).
                # Agent worktrees created by Claude Code won't have entries
                # in this table, so they'll be processed normally.
                worktree_abs = str(worktree_dir.resolve())
                live_sessions = self.store.list_live_sessions_by_worktree(worktree_abs)
                if live_sessions:
                    skipped_live.append(worktree_name)
                    logger.bind(
                        domain="check",
                        worktree=worktree_name,
                        session_count=len(live_sessions),
                    ).info("Skipped agent worktree with live runtime sessions")
                    continue

                # Properly remove worktree: cleans git metadata AND directory
                remove_worktree(worktree_dir, force=True)
                cleaned.append(worktree_name)
                logger.bind(domain="check", worktree=worktree_name).info(
                    "Deleted expired agent worktree"
                )

            except Exception as exc:
                failed.append(f"{worktree_name}: {exc}")
                logger.bind(domain="check", worktree=worktree_name).warning(
                    f"Failed to clean agent worktree: {exc}"
                )

        return {"cleaned": cleaned, "skipped_live": skipped_live, "failed": failed}
