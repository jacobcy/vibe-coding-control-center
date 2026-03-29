"""Worktree resolution mixin for Orchestra dispatcher."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.orchestra.config import OrchestraConfig


class WorktreeResolverMixin:
    """Mixin providing worktree resolution utilities for dispatchers.

    Requires the host class to provide:
        - ``repo_path`` (Path): repository root path
        - ``config`` (OrchestraConfig): orchestra configuration
    """

    repo_path: Path
    config: OrchestraConfig

    def _resolve_manager_cwd(self, issue_number: int, flow_branch: str) -> Path | None:
        """Resolve stable cwd for manager execution on a flow branch.

        Priority:
        1. Current repo_path when already on flow branch
        2. Existing worktree that has the flow branch checked out
        3. Create a dedicated orchestra worktree for this issue branch
        """
        if self._is_current_branch(flow_branch):
            return self.repo_path

        existing = self._find_worktree_for_branch(flow_branch)
        if existing:
            return existing

        return self._ensure_manager_worktree(issue_number, flow_branch)

    def _normalize_manager_command(self, cmd: list[str], cwd: Path) -> list[str]:
        """Backwards-compatible manager command normalization.

        Some target branches may not yet support `vibe3 run --worktree`.
        In that case, drop the flag and continue execution to avoid hard fail.
        """
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
        """Check whether `vibe3 run` in target cwd supports `--worktree`."""
        try:
            result = subprocess.run(
                ["uv", "run", "python", "-m", "vibe3", "run", "--help"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception:
            return False

        if result.returncode != 0:
            return False
        return "--worktree" in result.stdout

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

    def _ensure_manager_worktree(self, issue_number: int, branch: str) -> Path | None:
        """Create dedicated manager worktree for issue flow branch when missing."""
        target = self.repo_path / ".worktrees" / f"issue-{issue_number}"

        if target.exists():
            logger.bind(
                domain="orchestra",
                issue=issue_number,
                branch=branch,
                worktree=str(target),
            ).warning("Manager worktree path already exists; cannot auto-create")
            return None

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
            return None

        if result.returncode != 0:
            logger.bind(
                domain="orchestra",
                issue=issue_number,
                branch=branch,
                worktree=str(target),
            ).warning(f"Failed to create manager worktree: {result.stderr.strip()}")
            return None

        logger.bind(
            domain="orchestra",
            issue=issue_number,
            branch=branch,
            worktree=str(target),
        ).info("Created manager worktree for flow branch")
        return target

    def _resolve_review_cwd(self, pr_number: int) -> Path:
        """Resolve best worktree cwd for PR review execution.

        Priority:
        1. Worktree that currently has PR head branch checked out
        2. Dispatcher default repo_path
        """
        try:
            from vibe3.clients.github_client import GitHubClient

            pr = GitHubClient().get_pr(pr_number)
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
