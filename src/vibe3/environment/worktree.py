"""Worktree management for environment isolation."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger

from vibe3.environment.worktree_manager_compat import ManagerCompatMixin
from vibe3.exceptions import SystemError

if TYPE_CHECKING:
    from vibe3.manager.flow_manager import FlowManager
    from vibe3.models.orchestra_config import OrchestraConfig


@dataclass
class WorktreeContext:
    """Context for a git worktree resource."""

    path: Path
    is_temporary: bool
    branch: Optional[str] = None
    issue_number: Optional[int] = None  # For tracking temporary worktrees


class WorktreeManager(ManagerCompatMixin):
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
        self._capability_cache: dict[Path, bool] = {}

    # --- Issue Worktree Methods (L3) ---

    def acquire_issue_worktree(
        self,
        issue_number: int,
        branch: str,
    ) -> WorktreeContext:
        """Acquire or create an issue-bound worktree (L3).

        This is the canonical method for L3 manager/plan/run/review execution.
        The worktree is bound to the flow branch and persisted across sessions.

        Args:
            issue_number: GitHub issue number
            branch: Git branch name for the worktree

        Returns:
            WorktreeContext with the worktree path and metadata

        Raises:
            SystemError: If worktree creation fails
        """
        # Check if already exists
        existing = self._find_worktree_for_branch(branch)
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

        # Create new worktree
        wt_path = self.repo_path / ".worktrees" / branch
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
        self._recycle_worktree_path(context.path)

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
            self._recycle_worktree_path(wt_path)

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
        self._recycle_worktree_path(context.path)

    # --- Internal Implementation ---

    def _create_issue_worktree(
        self,
        wt_path: Path,
        branch: str,
        issue_number: int,
    ) -> WorktreeContext:
        """Create an issue-bound worktree."""
        wt_path.parent.mkdir(parents=True, exist_ok=True)

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

        try:
            result = subprocess.run(
                ["git", "worktree", "add", str(wt_path), base_branch],
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

        return WorktreeContext(
            path=wt_path,
            is_temporary=True,
            branch=base_branch,
            issue_number=issue_number,
        )

    def _recycle_worktree_path(self, target: Path) -> None:
        """Recycle a worktree path, unregistering it first."""
        # Safety check: verify no active tmux session is using this worktree
        try:
            sessions = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}:#{session_path}"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if sessions.returncode == 0:
                for line in sessions.stdout.strip().split("\n"):
                    if not line:
                        continue
                    # Check if session path matches or contains target worktree
                    if ":" in line:
                        session_name, session_path = line.split(":", 1)
                        if str(target) in session_path or session_path.startswith(
                            str(target)
                        ):
                            logger.warning(
                                "Skipping worktree cleanup: active tmux session found",
                                worktree=str(target),
                                session=session_name,
                                session_path=session_path,
                            )
                            return
        except FileNotFoundError:
            # tmux not installed, proceed with cleanup
            pass
        except Exception as exc:
            logger.warning(
                "Failed to check tmux sessions, proceeding with cleanup",
                error=str(exc),
                worktree=str(target),
            )

        # Proceed with worktree removal
        try:
            result = subprocess.run(
                ["git", "worktree", "remove", str(target), "--force"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                logger.info("Removed worktree via git", path=str(target))
                return
        except Exception:
            pass

        # Fallback: prune and delete directory
        try:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception:
            pass

        if target.exists():
            shutil.rmtree(target)
            logger.info("Forcefully removed worktree directory", path=str(target))

    def _find_worktree_for_branch(self, branch: str) -> Optional[Path]:
        """Find existing worktree for a branch."""
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception:
            return None

        if result.returncode != 0:
            return None

        # Parse worktree list output
        current_path = None
        current_branch = None
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                current_path = Path(line.split(" ", 1)[1])
            elif line.startswith("branch "):
                # Extract branch name from refs/heads/<branch>
                full_branch = line.split(" ", 1)[1]
                # Strip refs/heads/ prefix if present
                if full_branch.startswith("refs/heads/"):
                    current_branch = full_branch[len("refs/heads/") :]
                else:
                    current_branch = full_branch
                if current_branch == branch and current_path:
                    return current_path

        return None
