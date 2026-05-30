"""Worktree lifecycle implementation details.

Extracted from worktree.py to keep file size manageable.
Contains low-level worktree creation and validation logic.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.environment.worktree_context import WorktreeContext
from vibe3.environment.worktree_support import (
    find_worktree_by_path,
    initialize_worktree,
    recycle_worktree_path,
)
from vibe3.exceptions import SystemError

if TYPE_CHECKING:
    from vibe3.models.orchestra_config import OrchestraConfig


def _is_auto_task_branch(branch: str) -> bool:
    """Check if branch follows auto-managed task naming convention."""
    return branch.startswith("task/issue-")


class WorktreeLifecycle:
    """Low-level worktree creation and validation operations.

    This class handles the implementation details of worktree lifecycle:
    - Creating issue and temporary worktrees
    - Validating branch names and issue numbers
    - Recording worktree paths to flow state
    """

    def __init__(self, config: "OrchestraConfig", repo_path: Path):
        """Initialize lifecycle handler.

        Args:
            config: Orchestra configuration
            repo_path: Path to the main repository
        """
        self.config = config
        self.repo_path = repo_path

    def create_issue_worktree(
        self,
        wt_path: Path,
        branch: str,
        issue_number: int,
    ) -> WorktreeContext:
        """Create an issue-bound worktree.

        Args:
            wt_path: Target path for the worktree
            branch: Git branch name
            issue_number: GitHub issue number

        Returns:
            WorktreeContext with the created worktree

        Raises:
            SystemError: If worktree creation fails
        """
        from vibe3.environment.worktree_support import find_worktree_for_branch

        wt_path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-flight: cleanup stale references
        self._prune_worktrees()

        if wt_path.exists():
            is_registered = find_worktree_by_path(self.repo_path, wt_path)

            if is_registered:
                if self.validate_branch_matches(wt_path, branch):
                    logger.info(
                        "Reusing existing registered worktree",
                        path=str(wt_path),
                        branch=branch,
                        issue=issue_number,
                    )
                    return WorktreeContext(
                        path=wt_path,
                        is_temporary=False,
                        branch=branch,
                        issue_number=issue_number,
                    )
                else:
                    logger.warning(
                        "Existing worktree has different branch, removing",
                        path=str(wt_path),
                        expected_branch=branch,
                    )
                    # recycle_worktree_path is git-aware: runs
                    # `git worktree remove --force` before rmtree,
                    # so both filesystem and git metadata are cleaned.
                    recycle_worktree_path(self.repo_path, wt_path)
            else:
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

    def create_temporary_worktree(
        self,
        wt_path: Path,
        base_branch: str,
        issue_number: int,
    ) -> WorktreeContext:
        """Create a temporary worktree.

        Args:
            wt_path: Target path for the worktree
            base_branch: Base branch to create from
            issue_number: GitHub issue number for tracking

        Returns:
            WorktreeContext with the created worktree

        Raises:
            SystemError: If worktree creation fails
        """
        wt_path.parent.mkdir(parents=True, exist_ok=True)

        # Pre-flight prune
        self._prune_worktrees()

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

    def record_worktree_path(self, branch: str, worktree_path: str) -> None:
        """Persist worktree path to flow_state for canonical tracking.

        Args:
            branch: Branch name
            worktree_path: Path to the worktree
        """
        try:
            git_common_dir = self.repo_path / ".git"
            vibe3_dir = git_common_dir / "vibe3"
            db_path = str(vibe3_dir / "handoff.db")
            store = SQLiteClient(db_path=db_path)
            store.update_flow_state(branch, worktree_path=worktree_path)
            logger.bind(
                domain="worktree",
                branch=branch,
                worktree_path=worktree_path,
            ).debug("Recorded worktree_path to flow_state")
        except Exception as exc:
            logger.bind(
                domain="worktree",
                branch=branch,
            ).warning(f"Failed to record worktree_path to flow_state: {exc}")

    def _prune_worktrees(self) -> None:
        """Clean up stale worktree references."""
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

    @staticmethod
    def validate_branch_matches(worktree_path: Path, expected_branch: str) -> bool:
        """Check that worktree's HEAD branch matches expected branch.

        Uses git rev-parse to resolve branch (works with both main repo
        and linked worktrees where .git is a gitdir pointer).

        Args:
            worktree_path: Path to the worktree
            expected_branch: Expected branch name

        Returns:
            True if branch matches, False otherwise
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            actual_branch = result.stdout.strip()
            return actual_branch == expected_branch
        except Exception:
            return False

    @staticmethod
    def validate_worktree_branch_for_issue(
        worktree_path: Path,
        issue_number: int,
        expected_branch: str,
    ) -> bool:
        """Validate that a worktree's branch name plausibly corresponds to the issue.

        The branch name should contain the issue number somewhere
        (e.g., task/issue-793, issue-793, dev/issue-793).

        Uses git rev-parse to resolve branch (works with linked worktrees).

        Args:
            worktree_path: Path to the worktree
            issue_number: Expected issue number
            expected_branch: Expected branch name

        Returns:
            True if branch plausibly corresponds to issue
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            actual_branch = result.stdout.strip()
            if actual_branch == expected_branch:
                return True
            expected_suffix = f"issue-{issue_number}"
            if expected_suffix in actual_branch:
                return True
            return False
        except Exception:
            return False

    def find_or_create_worktree_for_branch(
        self,
        issue_number: int,
        flow_branch: str,
        repo_path: Path,
        acquire_issue_worktree_func: Callable[[int, str], WorktreeContext],
        *,
        check_recorded_path: bool = True,
        check_current_branch: bool = True,
        validate_issue_number: bool = True,
    ) -> WorktreeContext | None:
        """Find existing or create new worktree for branch.

        This is the unified core logic used by both orchestra and skill entry.

        Priority:
        1. Recorded worktree_path (if check_recorded_path)
        2. Current branch (if check_current_branch)
        3. Find existing worktree
        4. Acquire new issue worktree

        Args:
            issue_number: GitHub issue number
            flow_branch: Git branch name
            repo_path: Path to main repository
            acquire_issue_worktree_func: Callback to acquire issue worktree
            check_recorded_path: Whether to check flow_state.worktree_path
            check_current_branch: Whether to check if already on flow_branch
            validate_issue_number: Whether to validate branch contains issue number

        Returns:
            WorktreeContext if successful, None if failed
        """
        from vibe3.environment.worktree_support import (
            find_worktree_for_branch,
            is_current_branch,
        )

        # Step 1: Try recorded worktree_path from flow_state
        if check_recorded_path:
            ctx = self._try_recorded_path(issue_number, flow_branch, repo_path)
            if ctx:
                return ctx

        # Step 2: Current branch
        if check_current_branch and is_current_branch(repo_path, flow_branch):
            return WorktreeContext(
                path=repo_path,
                is_temporary=False,
                branch=flow_branch,
                issue_number=issue_number,
            )

        # Step 3: Find existing worktree
        existing = find_worktree_for_branch(repo_path, flow_branch)
        if existing:
            if validate_issue_number and not self.validate_worktree_branch_for_issue(
                existing, issue_number, flow_branch
            ):
                logger.bind(
                    domain="worktree",
                    issue=issue_number,
                    branch=flow_branch,
                    worktree_path=str(existing),
                ).error("Existing worktree branch name does not match issue number")
                return None
            # Record worktree path for auto task branches only
            if check_recorded_path and _is_auto_task_branch(flow_branch):
                self.record_worktree_path(flow_branch, str(existing))
            return WorktreeContext(
                path=existing,
                is_temporary=False,
                branch=flow_branch,
                issue_number=issue_number,
            )

        # Step 4: Create new worktree
        try:
            ctx = acquire_issue_worktree_func(issue_number, flow_branch)
            # Record worktree path for auto task branches only
            if check_recorded_path and _is_auto_task_branch(flow_branch):
                self.record_worktree_path(flow_branch, str(ctx.path))
            return ctx
        except Exception as exc:
            logger.bind(
                domain="worktree",
                issue=issue_number,
                branch=flow_branch,
            ).error(f"Failed to create worktree: {exc}")
            return None

    def _try_recorded_path(
        self,
        issue_number: int,
        flow_branch: str,
        repo_path: Path,
    ) -> WorktreeContext | None:
        """Try to use recorded worktree_path from flow_state.

        Args:
            issue_number: GitHub issue number
            flow_branch: Git branch name
            repo_path: Path to main repository

        Returns:
            WorktreeContext if valid recorded path found, None otherwise
        """
        try:
            git_common_dir = repo_path / ".git"
            vibe3_dir = git_common_dir / "vibe3"
            db_path = str(vibe3_dir / "handoff.db")
            store = SQLiteClient(db_path=db_path)
            flow_state = store.get_flow_state(flow_branch)
            recorded_path = flow_state.get("worktree_path") if flow_state else None
            if recorded_path and isinstance(recorded_path, str):
                recorded = Path(recorded_path)
                if recorded.exists() and self.validate_branch_matches(
                    recorded, flow_branch
                ):
                    return WorktreeContext(
                        path=recorded,
                        is_temporary=False,
                        branch=flow_branch,
                        issue_number=issue_number,
                    )
                else:
                    logger.bind(
                        domain="worktree",
                        issue=issue_number,
                        branch=flow_branch,
                        recorded_path=str(recorded),
                    ).warning("Recorded worktree_path invalid (stale or wrong branch)")
        except Exception as exc:
            logger.bind(
                domain="worktree",
                issue=issue_number,
                branch=flow_branch,
            ).warning(f"Failed to read recorded worktree_path: {exc}")
        return None
