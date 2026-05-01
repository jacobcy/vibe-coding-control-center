"""Manager scene capabilities - observation and cleanup for flow scenes.

This module provides a pure capability layer for scene management.
It exposes observation and cleanup methods but does NOT make decisions
about when to cleanup. Decision logic belongs to orchestrator, manager
agent, or closeout skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.flow_cleanup_service import FlowCleanupService
    from vibe3.services.issue_flow_service import IssueFlowService


@dataclass
class SceneStatus:
    """Status snapshot of a flow scene.

    Attributes:
        branch: Branch name for the scene
        flow_status: Flow status (active, done, aborted, stale, None if no flow)
        has_worktree: Whether worktree exists for this branch
        has_local_branch: Whether local branch exists
        has_remote_branch: Whether remote branch exists
        has_handoff: Whether handoff files exist
        issue_number: Issue number parsed from branch (None if not a task branch)
    """

    branch: str
    flow_status: str | None
    has_worktree: bool
    has_local_branch: bool
    has_remote_branch: bool
    has_handoff: bool
    issue_number: int | None

    @property
    def is_terminal(self) -> bool:
        """Check if flow is in terminal state (done or aborted)."""
        return self.flow_status in ("done", "aborted")

    @property
    def is_retainable(self) -> bool:
        """Check if scene should be retained.

        A scene is retainable if:
        - Flow is active (not terminal), OR
        - Flow has no status but has worktree/local-branch (unmanaged work)

        Terminal flows (done/aborted) are NOT retainable.
        """
        if self.flow_status is None:
            # Unmanaged work - retain if has physical resources
            return self.has_worktree or self.has_local_branch
        # Managed flow - retain only if active
        return self.flow_status == "active"


@dataclass
class CleanupResult:
    """Result of cleanup operations.

    Mirrors FlowCleanupService.cleanup_flow_scene() return structure.
    """

    worktree: bool
    local_branch: bool
    remote_branch: bool
    handoff: bool
    flow_record: bool


class ManagerSceneCapabilities:
    """Scene cleanup capabilities for manager module.

    This is a pure capability layer - it provides the ability to cleanup
    and observe scene state, but does NOT make decisions about when to cleanup.
    Decision logic belongs to orchestrator, manager agent, or closeout skill.

    Example usage:
        # Observation
        caps = ManagerSceneCapabilities()
        status = caps.get_scene_status("task/issue-418")
        if status.is_terminal and not status.is_retainable:
            # Decision to cleanup belongs to caller
            caps.cleanup_scene("task/issue-418")

        # Cleanup
        result = caps.cleanup_scene("task/issue-418", include_remote=True)
        if all(result.values()):
            print("Cleanup successful")
    """

    def __init__(
        self,
        git_client: GitClient | None = None,
        store: SQLiteClient | None = None,
        flow_cleanup_service: FlowCleanupService | None = None,
        issue_flow_service: IssueFlowService | None = None,
    ) -> None:
        """Initialize ManagerSceneCapabilities.

        Args:
            git_client: Git client for branch/worktree operations
            store: SQLite client for database operations
            flow_cleanup_service: Service for cleanup operations
            issue_flow_service: Service for issue-flow mapping
        """
        from vibe3.clients.git_client import GitClient
        from vibe3.clients.sqlite_client import SQLiteClient

        self.git_client = git_client or GitClient()
        self.store = store or SQLiteClient()
        self._flow_cleanup_service = flow_cleanup_service
        self._issue_flow_service = issue_flow_service

    @property
    def flow_cleanup_service(self) -> FlowCleanupService:
        """Lazy-initialized flow cleanup service."""
        if self._flow_cleanup_service is None:
            from vibe3.services.flow_cleanup_service import FlowCleanupService

            self._flow_cleanup_service = FlowCleanupService(
                git_client=self.git_client,
                store=self.store,
                issue_flow_service=self._issue_flow_service,
            )
        return self._flow_cleanup_service

    @property
    def issue_flow_service(self) -> IssueFlowService:
        """Lazy-initialized issue-flow service."""
        if self._issue_flow_service is None:
            from vibe3.services.issue_flow_service import IssueFlowService

            self._issue_flow_service = IssueFlowService(store=self.store)
        return self._issue_flow_service

    # Observation methods

    def get_scene_status(self, branch: str) -> SceneStatus:
        """Get complete status snapshot for a scene.

        Args:
            branch: Branch name to check

        Returns:
            SceneStatus with complete state information
        """
        from vibe3.services.flow_service import FlowService
        from vibe3.utils.git_helpers import get_branch_handoff_dir
        from vibe3.utils.path_helpers import get_git_common_dir

        # Get flow status
        flow_service = FlowService(store=self.store)
        flow_state = flow_service.get_flow_state(branch)
        flow_status = flow_state.flow_status if flow_state else None

        # Check physical resources
        has_worktree = self._has_worktree(branch)
        has_local_branch = self.git_client.branch_exists(branch)
        has_remote_branch = self._has_remote_branch(branch)

        # Check handoff
        git_dir = get_git_common_dir(self.git_client)
        handoff_dir = get_branch_handoff_dir(git_dir, branch)
        has_handoff = handoff_dir.exists()

        # Parse issue number
        issue_number = self.issue_flow_service.parse_issue_number(branch)

        return SceneStatus(
            branch=branch,
            flow_status=flow_status,
            has_worktree=has_worktree,
            has_local_branch=has_local_branch,
            has_remote_branch=has_remote_branch,
            has_handoff=has_handoff,
            issue_number=issue_number,
        )

    def is_flow_terminal(self, branch: str) -> bool:
        """Check if flow is in terminal state (done or aborted).

        Args:
            branch: Branch name to check

        Returns:
            True if flow is done or aborted, False otherwise
        """
        status = self.get_scene_status(branch)
        return status.is_terminal

    def is_flow_retainable(self, branch: str) -> bool:
        """Check if scene should be retained.

        Args:
            branch: Branch name to check

        Returns:
            True if scene should be kept, False if safe to cleanup
        """
        status = self.get_scene_status(branch)
        return status.is_retainable

    def has_active_worktree(self, branch: str) -> bool:
        """Check if worktree exists for branch.

        Args:
            branch: Branch name to check

        Returns:
            True if worktree exists, False otherwise
        """
        return self._has_worktree(branch)

    def has_remote_branch(self, branch: str) -> bool:
        """Check if remote branch exists.

        Args:
            branch: Branch name to check

        Returns:
            True if remote branch exists, False otherwise
        """
        return self._has_remote_branch(branch)

    # Cleanup methods (wrap FlowCleanupService)

    def cleanup_scene(
        self,
        branch: str,
        *,
        include_remote: bool = True,
        terminate_sessions: bool = True,
        keep_flow_record: bool = False,
        force_delete: bool = False,
    ) -> CleanupResult:
        """Complete cleanup of a flow scene.

        Delegates to FlowCleanupService.cleanup_flow_scene().
        This is a full cleanup: worktree, branches, handoff, flow record.

        Args:
            branch: Branch name for the flow to clean up
            include_remote: Whether to also delete remote branch
            terminate_sessions: Whether to terminate tmux sessions
            keep_flow_record: Keep flow record (for done/merged flows)
            force_delete: Hard delete flow record (cannot recover)

        Returns:
            CleanupResult with success status for each step
        """
        logger.bind(
            domain="manager",
            action="cleanup_scene",
            branch=branch,
            include_remote=include_remote,
        ).info("Starting scene cleanup via capability layer")

        results = self.flow_cleanup_service.cleanup_flow_scene(
            branch,
            include_remote=include_remote,
            terminate_sessions=terminate_sessions,
            keep_flow_record=keep_flow_record,
            force_delete=force_delete,
        )

        return CleanupResult(**results)

    def cleanup_worktree_only(self, branch: str) -> bool:
        """Remove worktree only, keeping branches and flow record.

        Args:
            branch: Branch name to remove worktree for

        Returns:
            True if worktree removed or didn't exist, False on failure
        """
        logger.bind(
            domain="manager",
            action="cleanup_worktree_only",
            branch=branch,
        ).info("Removing worktree only")

        try:
            worktree_path = self.git_client.find_worktree_path_for_branch(branch)
            if worktree_path:
                self.git_client.remove_worktree(str(worktree_path), force=True)
                logger.bind(domain="manager", branch=branch).debug("Removed worktree")
            return True
        except Exception as exc:
            logger.bind(domain="manager", branch=branch).warning(
                f"Failed to remove worktree: {exc}"
            )
            return False

    def cleanup_branch_only(self, branch: str, include_remote: bool = False) -> bool:
        """Delete branches only, keeping worktree and flow record.

        Args:
            branch: Branch name to delete
            include_remote: Whether to also delete remote branch

        Returns:
            True if branches deleted or didn't exist, False on failure
        """
        logger.bind(
            domain="manager",
            action="cleanup_branch_only",
            branch=branch,
            include_remote=include_remote,
        ).info("Deleting branches only")

        success = True

        # Delete local branch
        try:
            if self.git_client.branch_exists(branch):
                self.git_client.delete_branch(branch, force=True)
                logger.bind(domain="manager", branch=branch).debug(
                    "Deleted local branch"
                )
        except Exception as exc:
            logger.bind(domain="manager", branch=branch).warning(
                f"Failed to delete local branch: {exc}"
            )
            success = False

        # Delete remote branch
        if include_remote:
            try:
                if self._has_remote_branch(branch):
                    self.git_client.delete_remote_branch(branch)
                    logger.bind(domain="manager", branch=branch).debug(
                        "Deleted remote branch"
                    )
            except Exception as exc:
                logger.bind(domain="manager", branch=branch).warning(
                    f"Failed to delete remote branch: {exc}"
                )
                success = False

        return success

    # Private helper methods

    def _has_worktree(self, branch: str) -> bool:
        """Check if worktree exists for branch."""
        try:
            path = self.git_client.find_worktree_path_for_branch(branch)
            return path is not None
        except Exception:
            return False

    def _has_remote_branch(self, branch: str) -> bool:
        """Check if remote branch exists."""
        try:
            result = self.git_client._run(
                ["branch", "-r", "--list", f"origin/{branch}"]
            )
            return bool(result.strip())
        except Exception:
            return False
