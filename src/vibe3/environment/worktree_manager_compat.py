"""Legacy manager compatibility methods for backward compatibility.

This module contains methods extracted from the original WorktreeManager
to maintain backward compatibility with ManagerExecutor and orchestration layer.

These methods will be gradually phased out as the architecture evolves.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

from loguru import logger

from vibe3.orchestra.logging import append_orchestra_event

if TYPE_CHECKING:
    from vibe3.environment.worktree import WorktreeContext
    from vibe3.manager.flow_manager import FlowManager
    from vibe3.models.orchestra_config import OrchestraConfig


class ManagerCompatMixin:
    """Legacy manager compatibility methods.

    These methods maintain backward compatibility with ManagerExecutor
    and orchestration layer expectations. They will be gradually
    deprecated as the architecture evolves.

    Usage:
        class WorktreeManager(ManagerCompatMixin):
            # Core methods + inherited compat methods

    Note:
        This mixin uses Protocol-style declarations for abstract methods.
        Subclasses must implement these methods for full functionality.
    """

    # Declare attributes that will be set by subclass
    # These are instance attributes, not class attributes
    if TYPE_CHECKING:
        config: "OrchestraConfig"
        repo_path: Path
        flow_manager: Optional["FlowManager"]
        _capability_cache: dict[Path, bool]

    # Abstract methods expected to be implemented by subclass
    def acquire_issue_worktree(
        self, issue_number: int, branch: str
    ) -> "WorktreeContext":
        """Abstract: Acquire issue-bound worktree (implemented by subclass)."""
        raise NotImplementedError("Subclass must implement acquire_issue_worktree")

    def _find_worktree_for_branch(self, branch: str) -> Optional[Path]:
        """Abstract: Find worktree for branch (implemented by subclass)."""
        raise NotImplementedError("Subclass must implement _find_worktree_for_branch")

    def _recycle_worktree_path(self, target: Path) -> None:
        """Abstract: Recycle worktree path (implemented by subclass)."""
        raise NotImplementedError("Subclass must implement _recycle_worktree_path")

    def resolve_manager_cwd(
        self, issue_number: int, flow_branch: str
    ) -> Tuple[Optional[Path], bool]:
        """Legacy method for manager_executor compatibility."""
        try:
            ctx = self.acquire_issue_worktree(issue_number, flow_branch)
            return ctx.path, False
        except Exception:
            return None, False

    def ensure_manager_worktree(
        self, issue_number: int, branch: str
    ) -> Tuple[Optional[Path], bool]:
        """Legacy method for manager_executor compatibility."""
        try:
            ctx = self.acquire_issue_worktree(issue_number, branch)
            return ctx.path, False
        except Exception:
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
