"""Worktree management for environment isolation."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

from loguru import logger

from vibe3.exceptions import SystemError
from vibe3.orchestra.logging import append_orchestra_event

if TYPE_CHECKING:
    from vibe3.manager.flow_manager import FlowManager
    from vibe3.orchestra.config import OrchestraConfig


@dataclass
class WorktreeContext:
    """Context for a git worktree resource."""

    path: Path
    is_temporary: bool
    branch: Optional[str] = None
    issue_number: Optional[int] = None  # For tracking temporary worktrees


class WorktreeManager:
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

    # --- Legacy Methods (for backward compatibility) ---

    def resolve_manager_cwd(
        self, issue_number: int, flow_branch: str
    ) -> Tuple[Optional[Path], bool]:
        """Legacy method for manager_executor compatibility."""
        try:
            ctx = self.acquire_issue_worktree(issue_number, flow_branch)
            return ctx.path, False
        except SystemError:
            return None, False

    def ensure_manager_worktree(
        self, issue_number: int, branch: str
    ) -> Tuple[Optional[Path], bool]:
        """Legacy method for manager_executor compatibility."""
        try:
            ctx = self.acquire_issue_worktree(issue_number, branch)
            return ctx.path, False
        except SystemError:
            return None, False

    def _resolve_manager_cwd(
        self, issue_number: int, flow_branch: str
    ) -> Tuple[Optional[Path], bool]:
        """Internal resolve implementation for backward compatibility."""
        if self._is_current_branch(flow_branch):
            return self.repo_path, False

        existing = self._find_worktree_for_branch(flow_branch)
        if existing:
            return existing, False

        return self._ensure_manager_worktree(issue_number, flow_branch)

    def _ensure_manager_worktree(
        self, issue_number: int, branch: str
    ) -> Tuple[Optional[Path], bool]:
        """Legacy internal method for backward compatibility.

        This method preserves the old behavior of checking for mismatched worktrees
        and recycling them before creating new ones.
        """
        target = self.repo_path / ".worktrees" / f"issue-{issue_number}"

        if target.exists():
            # Valid worktree: .git file present means git tracks it
            if (target / ".git").exists():
                registered = self._find_worktree_for_branch(branch)
                if registered == target:
                    logger.info(
                        "Reusing existing manager worktree",
                        issue=issue_number,
                        branch=branch,
                        worktree=str(target),
                    )
                    return target, False
                logger.warning(
                    "Recycling mismatched manager worktree path before auto-creation",
                    issue=issue_number,
                    branch=branch,
                    worktree=str(target),
                )
                self._recycle_worktree_path(target)
            else:
                logger.warning(
                    "Recycling orphan manager worktree path before auto-creation",
                    issue=issue_number,
                    branch=branch,
                    worktree=str(target),
                )
                self._recycle_worktree_path(target)

        # Create new worktree
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                ["git", "worktree", "add", str(target), branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            logger.error(
                "Failed to create manager worktree",
                issue=issue_number,
                branch=branch,
                error=str(exc),
            )
            return None, False

        if result.returncode != 0:
            logger.error(
                "Git worktree add failed",
                issue=issue_number,
                branch=branch,
                stderr=result.stderr,
            )
            return None, False

        logger.info(
            "Created manager worktree",
            issue=issue_number,
            branch=branch,
            path=str(target),
        )

        # Log orchestra event for backward compatibility
        append_orchestra_event(
            "worktree",
            (f"created issue #{issue_number} branch={branch} " f"path={target}"),
            repo_root=self.repo_path,
        )

        # Return True to indicate this is a newly created worktree
        return target, True

    def align_auto_scene_to_base(self, cwd: Path, flow_branch: str) -> bool:
        """Reset a canonical auto scene to the configured base ref."""
        if not flow_branch.startswith("task/issue-"):
            return True

        base_ref = str(
            getattr(self.config, "scene_base_ref", "origin/main") or ""
        ).strip()
        if not base_ref:
            return True

        # Check if branch already has commits (not a fresh branch)
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-n", "1", flow_branch],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            has_commits = result.returncode == 0 and result.stdout.strip()
        except Exception:
            has_commits = False

        if has_commits:
            # Existing branch with commits - only fetch, don't reset/clean
            logger.info(
                "Skipping destructive alignment for existing task branch with commits",
                branch=flow_branch,
                cwd=str(cwd),
            )
            commands = [
                ["git", "fetch", "--all", "--prune"],
            ]
        else:
            # Fresh branch - safe to align
            commands = [
                ["git", "fetch", "--all", "--prune"],
                ["git", "checkout", flow_branch],
                ["git", "reset", "--hard", base_ref],
                ["git", "clean", "-fd"],
            ]

        for cmd in commands:
            try:
                result = subprocess.run(
                    cmd,
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to align auto scene: {exc}",
                    branch=flow_branch,
                    cwd=str(cwd),
                    base_ref=base_ref,
                )
                return False
            if result.returncode != 0:
                logger.warning(
                    "Failed to align auto scene to base ref: "
                    f"{(result.stderr or result.stdout).strip()}",
                    branch=flow_branch,
                    cwd=str(cwd),
                    base_ref=base_ref,
                )
                return False

        logger.info(
            "Aligned auto scene to configured base ref",
            branch=flow_branch,
            cwd=str(cwd),
            base_ref=base_ref,
        )
        return True

    def normalize_manager_command(self, cmd: list[str], cwd: Path) -> list[str]:
        """Backwards-compatible manager command normalization."""
        return self._normalize_manager_command(cmd, cwd)

    def _normalize_manager_command(self, cmd: list[str], cwd: Path) -> list[str]:
        if "--worktree" not in cmd:
            return cmd
        if self._supports_run_worktree_option(cwd):
            return cmd

        logger.warning(
            "Target worktree does not support `vibe3 run --worktree`; "
            "falling back without the flag",
            cwd=str(cwd),
        )
        return [arg for arg in cmd if arg != "--worktree"]

    def recycle(self, path: Path) -> bool:
        """Remove a git worktree.

        Args:
            path: Path to the worktree to remove

        Returns:
            True if successful, False otherwise
        """
        if not path or not path.exists():
            return False

        try:
            # Check if it's actually a worktree
            if not (path / ".git").exists():
                logger.warning(
                    "Path is not a valid git worktree (no .git file)",
                    worktree=str(path),
                )
                return False

            result = subprocess.run(
                ["git", "worktree", "remove", str(path)],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.error(
                    f"Failed to remove worktree: {result.stderr.strip()}",
                    worktree=str(path),
                )
                return False

            logger.info("Worktree removed successfully", worktree=str(path))
            return True
        except Exception as exc:
            logger.error(f"Error removing worktree: {exc}", worktree=str(path))
            return False

    def _resolve_review_cwd(self, pr_number: int) -> Path:
        """Resolve best worktree cwd for PR review execution."""
        try:
            # Try to get GitHubClient from flow_manager if available
            github = getattr(self.flow_manager, "github", None)
            if github is None:
                from vibe3.clients.github_client import GitHubClient

                github = GitHubClient()

            pr = github.get_pr(pr_number)
            if not pr or not pr.head_branch:
                return self.repo_path

            worktree = self._find_worktree_for_branch(pr.head_branch)
            if worktree:
                logger.info(
                    "Resolved PR review to matching worktree",
                    pr_number=pr_number,
                    branch=pr.head_branch,
                    worktree=str(worktree),
                )
                return worktree
        except Exception as exc:
            logger.warning(
                f"Failed to resolve PR worktree for #{pr_number}: {exc}",
            )

        return self.repo_path

    # --- Helper Methods ---

    def _is_current_branch(self, branch: str) -> bool:
        """Check whether dispatcher repo_path currently points at the target branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except Exception:
            return False
        if result.returncode != 0:
            return False
        stripped: str = result.stdout.strip()
        return stripped == branch

    def _supports_run_worktree_option(self, cwd: Path) -> bool:
        """Check whether `vibe3 run` in target cwd supports `--worktree`.

        Result is cached per cwd to avoid repeated subprocess calls on
        every dispatch.
        """
        if cwd in self._capability_cache:
            return self._capability_cache[cwd]

        try:
            result = subprocess.run(
                ["uv", "run", "python", "-m", "vibe3", "run", "--help"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            self._capability_cache[cwd] = False
            return False

        supported = result.returncode == 0 and "--worktree" in result.stdout
        self._capability_cache[cwd] = supported
        return supported
