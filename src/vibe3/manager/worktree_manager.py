"""Worktree management for Orchestra manager."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.manager.flow_manager import FlowManager
    from vibe3.orchestra.config import OrchestraConfig


class WorktreeManager:
    """Manages worktrees for flow execution.

    Provides resolution, creation, and recycling of git worktrees.
    """

    def __init__(
        self,
        config: OrchestraConfig,
        repo_path: Path,
        flow_manager: FlowManager | None = None,
    ):
        self.config = config
        self.repo_path = repo_path
        self.flow_manager = flow_manager
        # Cache per-cwd capability detection to avoid repeated --help subprocess calls
        self._capability_cache: dict[Path, bool] = {}

    def resolve_manager_cwd(
        self, issue_number: int, flow_branch: str
    ) -> tuple[Path | None, bool]:
        """Resolve stable cwd for manager execution on a flow branch."""
        return self._resolve_manager_cwd(issue_number, flow_branch)

    def align_auto_scene_to_base(self, cwd: Path, flow_branch: str) -> bool:
        """Reset a canonical auto scene to the configured base ref."""
        return self._align_auto_scene_to_base(cwd, flow_branch)

    def _resolve_manager_cwd(
        self, issue_number: int, flow_branch: str
    ) -> tuple[Path | None, bool]:
        """Internal resolve implementation."""
        if self._is_current_branch(flow_branch):
            return self.repo_path, False

        existing = self._find_worktree_for_branch(flow_branch)
        if existing:
            return existing, False

        return self._ensure_manager_worktree(issue_number, flow_branch)

    def _align_auto_scene_to_base(self, cwd: Path, flow_branch: str) -> bool:
        """Align auto scene to base, but skip destructive operations.

        For existing task branches with commits, we only perform
        non-destructive operations (fetch) to avoid wiping out valid
        implementation work.
        """
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
            logger.bind(
                domain="orchestra",
                branch=flow_branch,
                cwd=str(cwd),
            ).info(
                "Skipping destructive alignment for existing task branch with commits"
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
                logger.bind(
                    domain="orchestra",
                    branch=flow_branch,
                    cwd=str(cwd),
                    base_ref=base_ref,
                ).warning(f"Failed to align auto scene: {exc}")
                return False
            if result.returncode != 0:
                logger.bind(
                    domain="orchestra",
                    branch=flow_branch,
                    cwd=str(cwd),
                    base_ref=base_ref,
                ).warning(
                    "Failed to align auto scene to base ref: "
                    f"{(result.stderr or result.stdout).strip()}"
                )
                return False

        logger.bind(
            domain="orchestra",
            branch=flow_branch,
            cwd=str(cwd),
            base_ref=base_ref,
        ).info("Aligned auto scene to configured base ref")
        return True

    def normalize_manager_command(self, cmd: list[str], cwd: Path) -> list[str]:
        """Backwards-compatible manager command normalization."""
        return self._normalize_manager_command(cmd, cwd)

    def _normalize_manager_command(self, cmd: list[str], cwd: Path) -> list[str]:
        if "--worktree" not in cmd:
            return cmd
        if self._supports_run_worktree_option(cwd):
            return cmd

        logger.bind(domain="orchestra", cwd=str(cwd)).warning(
            "Target worktree does not support `vibe3 run --worktree`; "
            "falling back without the flag"
        )
        return [arg for arg in cmd if arg != "--worktree"]

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

    def ensure_manager_worktree(
        self, issue_number: int, branch: str
    ) -> tuple[Path | None, bool]:
        """Create dedicated manager worktree for issue flow branch."""
        return self._ensure_manager_worktree(issue_number, branch)

    def _ensure_manager_worktree(
        self, issue_number: int, branch: str
    ) -> tuple[Path | None, bool]:
        target = self.repo_path / ".worktrees" / f"issue-{issue_number}"

        if target.exists():
            # Valid worktree: .git file present means git tracks it
            if (target / ".git").exists():
                logger.bind(
                    domain="orchestra",
                    issue=issue_number,
                    branch=branch,
                    worktree=str(target),
                ).info("Reusing existing manager worktree")
                return target, False
            logger.bind(
                domain="orchestra",
                issue=issue_number,
                branch=branch,
                worktree=str(target),
            ).warning(
                "Manager worktree path exists but has no .git file; "
                "remove it manually to allow auto-creation"
            )
            return None, False

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
            logger.bind(
                domain="orchestra",
                issue=issue_number,
                branch=branch,
                worktree=str(target),
            ).warning(f"Failed to create manager worktree: {exc}")
            return None, False

        if result.returncode != 0:
            logger.bind(
                domain="orchestra",
                issue=issue_number,
                branch=branch,
                worktree=str(target),
            ).warning(f"Failed to create manager worktree: {result.stderr.strip()}")
            return None, False

        logger.bind(
            domain="orchestra",
            issue=issue_number,
            branch=branch,
            worktree=str(target),
        ).info("Created manager worktree for flow branch")
        return target, True

    def resolve_review_cwd(self, pr_number: int) -> Path:
        """Resolve best worktree cwd for PR review execution."""
        return self._resolve_review_cwd(pr_number)

    def _resolve_review_cwd(self, pr_number: int) -> Path:
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
                logger.bind(
                    domain="orchestra",
                    pr_number=pr_number,
                    branch=pr.head_branch,
                    worktree=str(worktree),
                ).info("Resolved PR review to matching worktree")
                return worktree
        except Exception as exc:
            logger.bind(domain="orchestra").warning(
                f"Failed to resolve PR worktree for #{pr_number}: {exc}"
            )

        return self.repo_path

    def _find_worktree_for_branch(self, branch: str) -> Path | None:
        """Find worktree path whose checked-out branch matches ``branch``."""
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

        current_worktree: str | None = None
        current_branch: str | None = None

        def matched() -> Path | None:
            if current_worktree and current_branch == f"refs/heads/{branch}":
                return Path(current_worktree)
            return None

        for raw in result.stdout.splitlines():
            line = raw.strip()
            if not line:
                found = matched()
                if found:
                    return found
                current_worktree = None
                current_branch = None
                continue
            if line.startswith("worktree "):
                current_worktree = line.split(" ", 1)[1]
            elif line.startswith("branch "):
                current_branch = line.split(" ", 1)[1]

        final: Path | None = matched()
        return final

    def recycle(self, path: Path) -> bool:
        """Remove a git worktree.

        Args:
            path: Path to the worktree to remove

        Returns:
            True if successful, False otherwise
        """
        if not path or not path.exists():
            return False

        log = logger.bind(domain="orchestra", worktree=str(path))
        try:
            # Check if it's actually a worktree
            if not (path / ".git").exists():
                log.warning("Path is not a valid git worktree (no .git file)")
                return False

            result = subprocess.run(
                ["git", "worktree", "remove", str(path)],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                log.error(f"Failed to remove worktree: {result.stderr.strip()}")
                return False

            log.info("Worktree removed successfully")
            return True
        except Exception as exc:
            log.error(f"Error removing worktree: {exc}")
            return False
