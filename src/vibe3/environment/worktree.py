"""Worktree management for environment isolation and runtime path resolution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.environment.worktree_context import WorktreeContext
from vibe3.environment.worktree_lifecycle import WorktreeLifecycle
from vibe3.environment.worktree_pr_mixin import WorktreePRMixin
from vibe3.environment.worktree_support import (
    align_auto_scene_to_base,
    find_worktree_for_branch,
    recycle_worktree_path,
)
from vibe3.exceptions import SystemError
from vibe3.services.shared.paths import get_vibe3_db_path

if TYPE_CHECKING:
    from vibe3.clients import FlowStatePort
    from vibe3.models import OrchestraConfig


class WorktreeManager(WorktreePRMixin):
    """Unified manager for issue worktrees (L3) and temporary worktrees (L2).

    This manager is the SINGLE AUTHORITY for worktree allocation in vibe3.
    It enforces the runtime session semantics defined in
    vibe3-worktree-ownership-standard.md.

    Key responsibilities:
    - Issue worktrees (L3): Long-lived worktrees bound to flow branches
    - Temporary worktrees (L2): Ephemeral worktrees for safe isolation
    - Lifecycle management: Create, reuse, and cleanup worktrees
    """

    def __init__(
        self,
        config: "OrchestraConfig",
        repo_path: Path,
        flow_service: "FlowStatePort | None" = None,
    ):
        """Initialize WorktreeManager.

        Args:
            config: Orchestra configuration
            repo_path: Path to the main repository
            flow_service: FlowStatePort instance (optional, uses no-op if None)
        """
        self.config = config
        self.repo_path = repo_path
        self.flow_service: FlowStatePort | None = flow_service
        self.lifecycle = WorktreeLifecycle(config, repo_path, flow_service=flow_service)

    # --- Issue Worktree Methods (L3) ---

    def acquire_issue_worktree(
        self,
        issue_number: int,
        branch: str,
    ) -> WorktreeContext:
        """Acquire or create an issue-bound worktree (L3).

        This is the canonical method for L3 manager/plan/run/review execution.
        The worktree is bound to the flow branch and persisted across sessions.

        For flows woken up by dependency satisfaction, this will attempt to
        create the worktree from the dependency's PR head branch instead of main.
        If fetching the PR branch fails, it falls back to the standard creation.

        Args:
            issue_number: GitHub issue number
            branch: Git branch name for the worktree

        Returns:
            WorktreeContext with the worktree path and metadata

        Raises:
            SystemError: If worktree creation fails
        """
        # Check if already exists
        existing = find_worktree_for_branch(self.repo_path, branch)
        if existing:
            logger.info(
                "Reusing existing issue worktree",
                issue=issue_number,
                branch=branch,
                worktree=str(existing),
            )
            return WorktreeContext(
                path=existing,
                is_temporary=False,
                branch=branch,
                issue_number=issue_number,
            )

        # Check for dependency wake-up source PR
        wt_path = self.repo_path / ".worktrees" / branch
        source_pr_number = self._find_dependency_wakeup_pr(branch)

        if source_pr_number:
            # Try to create from PR branch
            context = self._create_from_pr_branch(
                wt_path, branch, issue_number, source_pr_number
            )
            if context:
                # Success! Return PR-based worktree
                return context

            # Failed, log and fall back to default
            logger.bind(
                issue=issue_number,
                branch=branch,
                source_pr=source_pr_number,
            ).warning(
                "Failed to create worktree from PR branch, falling back to origin/main"
            )

            # Record fallback event
            try:
                # Calculate db path directly from repo_path without git command
                git_common_dir = self.repo_path / ".git"
                db_path = str(get_vibe3_db_path(git_common_dir))
                store = SQLiteClient(db_path=db_path)
                store.add_event(
                    branch,
                    "dependency_branch_fallback",
                    "worktree:manager",
                    detail=f"Failed to fetch PR #{source_pr_number} branch, "
                    f"falling back to origin/main",
                    refs={"source_pr": str(source_pr_number)},
                )
            except Exception:
                # Failed to record event, but fallback still happens
                logger.bind(
                    issue=issue_number,
                    branch=branch,
                    source_pr=source_pr_number,
                ).warning("Failed to record fallback event")

        # Default: create from standard base (origin/main)
        return self.lifecycle.create_issue_worktree(wt_path, branch, issue_number)

    def release_issue_worktree(self, context: WorktreeContext) -> None:
        """Release an issue worktree (optional, typically kept for flow lifecycle).

        Issue worktrees are typically long-lived and bound to flow state.
        Call this only when the flow is complete or abandoned.

        Args:
            context: WorktreeContext to release
        """
        if context.is_temporary:
            logger.warning(
                "Attempted to release temporary worktree via issue method",
                path=str(context.path),
            )
            return

        logger.info(
            "Releasing issue worktree",
            path=str(context.path),
            branch=context.branch,
        )
        recycle_worktree_path(self.repo_path, context.path)

    # --- Temporary Worktree Methods (L2) ---

    def acquire_temporary_worktree(
        self,
        issue_number: int,
        base_branch: str = "main",
    ) -> WorktreeContext:
        """Acquire a temporary worktree for L2 supervisor/apply execution.

        This creates an ephemeral worktree for safe isolation during apply operations.
        The worktree is created fresh each time and should be released after use.

        Naming convention: .worktrees/tmp/{issue_number}

        Args:
            issue_number: GitHub issue number (for tracking)
            base_branch: Base branch to create worktree from

        Returns:
            WorktreeContext with the temporary worktree path

        Raises:
            SystemError: If worktree creation fails
        """
        wt_path = self.repo_path / ".worktrees" / "tmp" / str(issue_number)

        # Clean up existing temporary worktree for this issue (if any)
        if wt_path.exists():
            logger.warning(
                "Removing stale temporary worktree",
                issue=issue_number,
                path=str(wt_path),
            )
            recycle_worktree_path(self.repo_path, wt_path)

        # Create fresh temporary worktree
        return self.lifecycle.create_temporary_worktree(
            wt_path, base_branch, issue_number
        )

    def release_temporary_worktree(self, context: WorktreeContext) -> None:
        """Release a temporary worktree immediately after use.

        Temporary worktrees are always cleaned up after apply execution.
        This method ensures complete resource reclamation.

        Args:
            context: WorktreeContext to release
        """
        if not context.is_temporary:
            logger.warning(
                "Attempted to release issue worktree via temporary method",
                path=str(context.path),
            )
            return

        logger.info(
            "Releasing temporary worktree",
            path=str(context.path),
            issue=context.issue_number,
        )
        recycle_worktree_path(self.repo_path, context.path)

    # --- Manager Execution Compatibility ---

    def _find_or_create_worktree_for_branch(
        self,
        issue_number: int,
        flow_branch: str,
        *,
        check_recorded_path: bool = True,
        check_current_branch: bool = True,
        validate_issue_number: bool = True,
    ) -> WorktreeContext | None:
        """Shared core: find existing or create new worktree for branch.

        Delegates to WorktreeLifecycle for implementation.
        """
        return self.lifecycle.find_or_create_worktree_for_branch(
            issue_number,
            flow_branch,
            self.repo_path,
            self.acquire_issue_worktree,
            check_recorded_path=check_recorded_path,
            check_current_branch=check_current_branch,
            validate_issue_number=validate_issue_number,
        )

    def resolve_manager_cwd(
        self,
        issue_number: int,
        flow_branch: str,
    ) -> tuple[Path | None, bool]:
        """Resolve manager cwd for orchestra execution.

        Uses shared abstraction with full validation and flow_state recording.
        Returns (path, is_missing). Never raises — returns (None, False) on failure.
        """
        ctx = self._find_or_create_worktree_for_branch(
            issue_number,
            flow_branch,
            check_recorded_path=True,
            check_current_branch=True,
            validate_issue_number=True,
        )
        if ctx is None:
            return None, False

        # Align auto scene to base
        if self.align_auto_scene_to_base(ctx.path, flow_branch):
            return ctx.path, False
        return None, False

    def _resolve_manager_cwd(
        self,
        issue_number: int,
        flow_branch: str,
    ) -> tuple[Optional[Path], bool]:
        """Resolve manager cwd for role execution."""
        return self.resolve_manager_cwd(issue_number, flow_branch)

    def align_auto_scene_to_base(self, cwd: Path, flow_branch: str) -> bool:
        """Align auto task scenes to configured base ref when safe."""
        return align_auto_scene_to_base(self.config, cwd, flow_branch)

    def resolve_bootstrap_worktree_context(
        self,
        *,
        branch: str,
        issue_number: int,
        use_worktree: bool,
    ) -> WorktreeContext:
        """Resolve worktree context for vibe-new bootstrap.

        Uses shared abstraction with skill-specific behavior:
        - Full validation for issue number
        - Record worktree_path to flow_state
        - Align to base branch

        This ensures orchestra (task/issue-XXX) and skill (dev/issue-XXX)
        use identical worktree resolution logic, differing only in branch prefix.

        Args:
            branch: Target branch name (dev/issue-XXX)
            issue_number: GitHub issue number
            use_worktree: Whether to use a physical worktree

        Returns:
            WorktreeContext describing the execution environment
        """
        if not use_worktree:
            # Current repo path, no worktree creation
            return WorktreeContext(
                path=self.repo_path,
                is_temporary=False,
                branch=branch,
                issue_number=issue_number,
            )

        # Use shared abstraction: find existing or create new worktree
        ctx = self._find_or_create_worktree_for_branch(
            issue_number,
            branch,
            check_recorded_path=True,
            check_current_branch=False,  # Skill entry: always ask user first
            validate_issue_number=True,
        )

        if ctx is None:
            # CRITICAL: When use_worktree=True, creation failure must raise
            # error. User explicitly requested worktree isolation, MUST NOT
            # silently fallback to repo_path. Returning repo_path violates
            # isolation requirement and confuses flow management.
            logger.bind(
                domain="worktree",
                issue=issue_number,
                branch=branch,
            ).error("Worktree creation failed while use_worktree=True")
            raise SystemError(
                f"Failed to create worktree for issue #{issue_number} "
                f"branch {branch}. User requested worktree isolation but "
                "creation failed. Check git worktree status and disk space."
            )

        # Align to base for bootstrap entry
        if not self.align_auto_scene_to_base(ctx.path, branch):
            logger.bind(
                domain="worktree",
                issue=issue_number,
                branch=branch,
                worktree_path=str(ctx.path),
            ).error("Failed to align worktree to base branch")
            raise SystemError(
                f"Failed to align worktree to base branch for issue #{issue_number}. "
                f"Worktree created at {ctx.path} but alignment to {branch} failed. "
                "Check git status and scene_base_ref configuration."
            )
        return ctx
