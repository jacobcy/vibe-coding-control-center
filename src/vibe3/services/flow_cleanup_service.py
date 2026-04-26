"""Flow cleanup service - unified scene cleanup for terminal flows.

This service provides complete cleanup of flow scenes including:
- Worktree removal
- Local/remote branch deletion
- Handoff cleanup
- Flow record deletion

Used by both `task resume` and `check --clean-branch` to ensure consistent behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow_service import FlowService
    from vibe3.services.issue_flow_service import IssueFlowService


class FlowCleanupService:
    """Unified service for complete flow scene cleanup.

    This service coordinates the full cleanup of a flow scene:
    1. Terminate tmux sessions (if any)
    2. Remove worktree
    3. Delete local branch
    4. Delete remote branch
    5. Clear handoff files
    6. Delete flow record from database

    The cleanup is best-effort - failures are logged but don't stop
    the process from attempting remaining steps.
    """

    def __init__(
        self,
        git_client: GitClient | None = None,
        store: SQLiteClient | None = None,
        flow_service: FlowService | None = None,
        issue_flow_service: IssueFlowService | None = None,
    ) -> None:
        """Initialize flow cleanup service.

        Args:
            git_client: Git client for branch/worktree operations
            store: SQLite client for database operations
            flow_service: Service for flow lifecycle
            issue_flow_service: Service for issue-flow mapping
        """
        from vibe3.clients.git_client import GitClient
        from vibe3.clients.sqlite_client import SQLiteClient

        self.git_client = git_client or GitClient()
        self.store = store or SQLiteClient()
        self._flow_service = flow_service
        self._issue_flow_service = issue_flow_service

    @property
    def flow_service(self) -> FlowService:
        """Lazy-initialized flow service."""
        if self._flow_service is None:
            from vibe3.services.flow_service import FlowService

            self._flow_service = FlowService(store=self.store)
        return self._flow_service

    @property
    def issue_flow_service(self) -> IssueFlowService:
        """Lazy-initialized issue-flow service."""
        if self._issue_flow_service is None:
            from vibe3.services.issue_flow_service import IssueFlowService

            self._issue_flow_service = IssueFlowService(store=self.store)
        return self._issue_flow_service

    def cleanup_flow_scene(
        self,
        branch: str,
        *,
        include_remote: bool = True,
        terminate_sessions: bool = True,
    ) -> dict[str, bool]:
        """Complete cleanup of a flow scene.

        This method performs all cleanup steps for a terminal flow.
        Failures in individual steps are logged but don't prevent
        other steps from being attempted.

        Args:
            branch: Branch name for the flow to clean up
            include_remote: Whether to also delete remote branch
            terminate_sessions: Whether to terminate tmux sessions

        Returns:
            Dict with success status for each step:
                - worktree: True if removed or didn't exist
                - local_branch: True if deleted or didn't exist
                - remote_branch: True if deleted, didn't exist, or skipped
                - handoff: True if cleared or didn't exist
                - flow_record: True if deleted
        """
        results: dict[str, bool] = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }

        logger.bind(
            domain="cleanup",
            action="cleanup_flow_scene",
            branch=branch,
            include_remote=include_remote,
        ).info("Starting flow scene cleanup")

        # Step 1: Terminate tmux sessions (for task branches)
        if terminate_sessions and self.issue_flow_service.is_task_branch(branch):
            self._terminate_task_sessions(branch)

        # Step 2: Remove worktree
        try:
            worktree_path = self.git_client.find_worktree_path_for_branch(branch)
            if worktree_path:
                self.git_client.remove_worktree(str(worktree_path), force=True)
                logger.bind(domain="cleanup", branch=branch).debug("Removed worktree")
        except Exception as exc:
            logger.bind(domain="cleanup", branch=branch).warning(
                f"Failed to remove worktree: {exc}"
            )
            results["worktree"] = False

        # Step 3: Delete local branch
        try:
            if self.git_client.branch_exists(branch):
                self.git_client.delete_branch(branch, force=True, skip_if_worktree=True)
                logger.bind(domain="cleanup", branch=branch).debug(
                    "Deleted local branch"
                )
        except Exception as exc:
            logger.bind(domain="cleanup", branch=branch).warning(
                f"Failed to delete local branch: {exc}"
            )
            results["local_branch"] = False

        # Step 4: Delete remote branch
        if include_remote:
            try:
                if self._has_remote_branch(branch):
                    self.git_client.delete_remote_branch(branch)
                    logger.bind(domain="cleanup", branch=branch).debug(
                        "Deleted remote branch"
                    )
            except Exception as exc:
                logger.bind(domain="cleanup", branch=branch).warning(
                    f"Failed to delete remote branch: {exc}"
                )
                results["remote_branch"] = False

        # Step 5: Clear handoff files
        try:
            from vibe3.services.handoff_service import HandoffService

            HandoffService(
                store=self.store, git_client=self.git_client
            ).storage.clear_handoff_for_branch(branch)
            logger.bind(domain="cleanup", branch=branch).debug("Cleared handoff files")
        except Exception as exc:
            logger.bind(domain="cleanup", branch=branch).warning(
                f"Failed to clear handoff: {exc}"
            )
            results["handoff"] = False

        # Step 6: Delete flow record (always do this, even if other steps failed)
        try:
            self.flow_service.delete_flow(branch)
            logger.bind(domain="cleanup", branch=branch).info("Deleted flow record")
        except Exception as exc:
            logger.bind(domain="cleanup", branch=branch).warning(
                f"Failed to delete flow record: {exc}"
            )
            results["flow_record"] = False

        success_count = sum(1 for v in results.values() if v)
        logger.bind(
            domain="cleanup",
            branch=branch,
            success_count=success_count,
            total_steps=len(results),
        ).info(f"Flow scene cleanup completed ({success_count}/{len(results)} steps)")

        return results

    def _has_remote_branch(self, branch: str) -> bool:
        """Check if remote branch exists."""
        try:
            result = self.git_client._run(
                ["branch", "-r", "--list", f"origin/{branch}"]
            )
            return bool(result.strip())
        except Exception:
            return False

    def _terminate_task_sessions(self, branch: str) -> None:
        """Kill lingering tmux sessions for a task issue."""
        import subprocess

        from vibe3.environment.session_naming import get_manager_session_name

        issue_number = self.issue_flow_service.parse_issue_number(branch)
        if issue_number is None:
            return

        prefixes = (
            get_manager_session_name(issue_number),
            f"vibe3-plan-issue-{issue_number}",
            f"vibe3-run-issue-{issue_number}",
            f"vibe3-review-issue-{issue_number}",
        )

        try:
            result = subprocess.run(
                ["tmux", "ls"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except FileNotFoundError:
            return
        except Exception as exc:
            logger.bind(domain="cleanup", branch=branch).warning(
                f"Failed to inspect tmux sessions: {exc}"
            )
            return

        if result.returncode != 0:
            return

        active_sessions: list[str] = []
        for line in result.stdout.splitlines():
            session_name = line.split(":", 1)[0].strip()
            if any(
                session_name == prefix or session_name.startswith(f"{prefix}-")
                for prefix in prefixes
            ):
                active_sessions.append(session_name)

        for session_name in active_sessions:
            subprocess.run(
                ["tmux", "kill-session", "-t", session_name],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

        if active_sessions:
            logger.bind(domain="cleanup", branch=branch).debug(
                f"Terminated {len(active_sessions)} tmux sessions"
            )
