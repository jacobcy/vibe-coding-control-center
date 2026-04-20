"""Worktree management for environment isolation."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.worktree_pr_mixin import WorktreePRMixin
from vibe3.environment.worktree_support import (
    align_auto_scene_to_base,
    find_worktree_by_path,
    find_worktree_for_branch,
    initialize_worktree,
    is_current_branch,
    recycle_worktree_path,
)
from vibe3.exceptions import SystemError

if TYPE_CHECKING:
    from vibe3.execution.flow_dispatch import FlowManager
    from vibe3.models.orchestra_config import OrchestraConfig


@dataclass
class WorktreeContext:
    """Context for a git worktree resource."""

    path: Path
    is_temporary: bool
    branch: Optional[str] = None
    issue_number: Optional[int] = None  # For tracking temporary worktrees


class WorktreeManager(WorktreePRMixin):
    """Unified manager for issue worktrees (L3) and temporary worktrees (L2).

    This manager is the SINGLE AUTHORITY for worktree allocation in vibe3.
    It enforces the ownership semantics defined in vibe3-worktree-ownership-standard.md.

    Key responsibilities:
    - Issue worktrees (L3): Long-lived worktrees bound to flow branches
    - Temporary worktrees (L2): Ephemeral worktrees for safe isolation
    - Lifecycle management: Create, reuse, and cleanup worktrees
    """

    def __init__(
        self,
        config: "OrchestraConfig",
        repo_path: Path,
        flow_manager: Optional["FlowManager"] = None,
    ):
        """Initialize WorktreeManager.

        Args:
            config: Orchestra configuration
            repo_path: Path to the main repository
            flow_manager: Optional FlowManager for flow state binding
        """
        self.config = config
        self.repo_path = repo_path
        self.flow_manager = flow_manager

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
                vibe3_dir = git_common_dir / "vibe3"
                db_path = str(vibe3_dir / "handoff.db")
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
        return self._create_issue_worktree(wt_path, branch, issue_number)

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
        return self._create_temporary_worktree(wt_path, base_branch, issue_number)

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

    def resolve_manager_cwd(
        self,
        issue_number: int,
        flow_branch: str,
    ) -> tuple[Optional[Path], bool]:
        """Resolve manager cwd using canonical worktree ownership."""
        if is_current_branch(self.repo_path, flow_branch):
            return self.repo_path, False

        existing = find_worktree_for_branch(self.repo_path, flow_branch)
        if existing:
            if self.align_auto_scene_to_base(existing, flow_branch):
                return existing, False
            return None, False

        try:
            ctx = self.acquire_issue_worktree(issue_number, flow_branch)
            if self.align_auto_scene_to_base(ctx.path, flow_branch):
                return ctx.path, False
            return None, False
        except Exception:
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

    def _create_issue_worktree(
        self,
        wt_path: Path,
        branch: str,
        issue_number: int,
    ) -> WorktreeContext:
        """Create an issue-bound worktree."""
        wt_path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-flight: cleanup stale references
        try:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except Exception:
            pass

        # If path exists but is not registered, delete it
        if wt_path.exists() and not find_worktree_by_path(self.repo_path, wt_path):
            logger.warning(
                "Deleting unregistered directory at target worktree path",
                path=str(wt_path),
            )
            shutil.rmtree(wt_path)

        try:
            result = subprocess.run(
                ["git", "worktree", "add", str(wt_path), branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            logger.error(
                "Failed to create issue worktree",
                issue=issue_number,
                branch=branch,
                error=str(exc),
            )
            raise SystemError(f"Failed to create issue worktree: {exc}") from exc

        if result.returncode != 0:
            # Handle "already checked out" error
            if "already checked out" in result.stderr:
                logger.warning(
                    "Branch already checked out elsewhere, attempting to resolve",
                    branch=branch,
                )
                # Attempt to find where it is checked out
                existing_path = find_worktree_for_branch(self.repo_path, branch)
                if existing_path:
                    logger.info("Reusing worktree", path=str(existing_path))
                    return WorktreeContext(
                        path=existing_path,
                        is_temporary=False,
                        branch=branch,
                        issue_number=issue_number,
                    )

            logger.error(
                "Git worktree add failed",
                issue=issue_number,
                branch=branch,
                stderr=result.stderr,
            )
            raise SystemError(f"Git worktree add failed: {result.stderr.strip()}")

        logger.info(
            "Created issue worktree",
            issue=issue_number,
            branch=branch,
            path=str(wt_path),
        )
        initialize_worktree(self.repo_path, wt_path, reason="issue")

        return WorktreeContext(
            path=wt_path,
            is_temporary=False,
            branch=branch,
            issue_number=issue_number,
        )

    def _create_temporary_worktree(
        self,
        wt_path: Path,
        base_branch: str,
        issue_number: int,
    ) -> WorktreeContext:
        """Create a temporary worktree."""
        wt_path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-flight prune
        try:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.repo_path,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except Exception:
            pass

        if wt_path.exists():
            shutil.rmtree(wt_path)

        try:
            # Use --detach for temporary worktrees to allow multiple from same base
            result = subprocess.run(
                ["git", "worktree", "add", "--detach", str(wt_path), base_branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            logger.error(
                "Failed to create temporary worktree",
                issue=issue_number,
                base=base_branch,
                error=str(exc),
            )
            raise SystemError(f"Failed to create temporary worktree: {exc}") from exc

        if result.returncode != 0:
            logger.error(
                "Git worktree add failed for temporary worktree",
                issue=issue_number,
                base=base_branch,
                stderr=result.stderr,
            )
            raise SystemError(f"Git worktree add failed: {result.stderr.strip()}")

        logger.info(
            "Created temporary worktree",
            issue=issue_number,
            base=base_branch,
            path=str(wt_path),
        )
        initialize_worktree(self.repo_path, wt_path, reason="temporary")

        return WorktreeContext(
            path=wt_path,
            is_temporary=True,
            branch=base_branch,
            issue_number=issue_number,
        )
