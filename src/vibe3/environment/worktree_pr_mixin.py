"""PR-based worktree creation mixin for WorktreeManager.

Extracted from worktree.py to keep file size manageable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.environment.worktree_context import WorktreeContext

if TYPE_CHECKING:
    from vibe3.models.orchestra_config import OrchestraConfig


class WorktreePRMixin:
    """Mixin for PR-based worktree creation functionality.

    Provides methods to create worktrees from dependency PR branches,
    supporting the "continue development from dependency PR" workflow.
    """

    # These are expected to be provided by the main class
    repo_path: Path
    config: "OrchestraConfig"

    def _find_dependency_wakeup_pr(self, flow_branch: str) -> Optional[int]:
        """Find the source PR number from dependency wake-up event history.

        Args:
            flow_branch: The flow branch to check

        Returns:
            PR number if flow has dependency wake-up event with source_pr,
            None otherwise
        """
        try:
            # Calculate db path directly from repo_path without git command
            # This avoids extra git invocation in unit tests
            git_common_dir = self.repo_path / ".git"
            vibe3_dir = git_common_dir / "vibe3"
            db_path = str(vibe3_dir / "handoff.db")
            store = SQLiteClient(db_path=db_path)
            events = store.get_events(flow_branch, event_type="flow_unblocked")
        except Exception:
            # Failed to access SQLite store (e.g. in test temp directory)
            # Return None, fall back to default behavior
            return None

        if not events:
            return None

        # Find the most recent wake-up event
        # get_events already orders by created_at DESC (newest first)
        for event in events:
            refs = event.get("refs")
            if refs is None:
                continue
            source_pr = refs.get("source_pr")
            if source_pr:
                try:
                    return int(source_pr)
                except (ValueError, TypeError):
                    continue

        return None

    def _fetch_pr_branch(self, pr_number: int) -> Optional[str]:
        """Fetch PR head branch and verify it's accessible.

        Args:
            pr_number: The PR number to fetch

        Returns:
            Head branch name if fetch succeeds, None otherwise
        """
        gh = GitHubClient()
        pr = gh.get_pr(pr_number=pr_number)

        if not pr:
            logger.bind(pr_number=pr_number).warning(
                "Could not retrieve PR information for dependency branch creation"
            )
            return None

        head_branch = pr.head_branch
        if not head_branch:
            logger.bind(pr_number=pr_number).warning("PR has no head branch name")
            return None

        # Fetch the PR branch
        try:
            result = subprocess.run(
                [
                    "git",
                    "fetch",
                    "origin",
                    f"+refs/heads/{head_branch}:refs/remotes/origin/{head_branch}",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception as exc:
            logger.bind(
                pr_number=pr_number,
                head_branch=head_branch,
                error=str(exc),
            ).warning("Exception while fetching PR branch")
            return None

        if result.returncode != 0:
            logger.bind(
                pr_number=pr_number,
                head_branch=head_branch,
                stderr=result.stderr,
            ).warning("Failed to fetch PR branch from origin")
            return None

        logger.bind(
            pr_number=pr_number,
            head_branch=head_branch,
        ).info("Successfully fetched PR branch for dependency base")
        return head_branch

    def _branch_exists_locally(self, branch: str) -> bool:
        """Check if a local branch exists (regardless of worktree registration).

        Args:
            branch: Branch name to check

        Returns:
            True if the branch exists locally
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _create_from_pr_branch(
        self,
        wt_path: Path,
        branch: str,
        issue_number: int,
        pr_number: int,
    ) -> Optional["WorktreeContext"]:
        """Create worktree from PR head branch.

        Attempts to fetch PR head branch and create worktree from it.
        Falls back to None if fetch fails, caller should handle fallback to main.

        Args:
            wt_path: Target worktree path
            branch: New branch name for the worktree
            issue_number: Issue number for tracking
            pr_number: PR number to create from

        Returns:
            WorktreeContext if creation succeeded, None otherwise
            (caller should fallback)
        """
        from vibe3.environment.worktree_support import (
            find_worktree_by_path,
            initialize_worktree,
        )

        # Fetch PR branch
        head_branch = self._fetch_pr_branch(pr_number)
        if not head_branch:
            # Fetch failed, will fallback
            return None

        # Check if path needs cleanup
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
            import shutil

            shutil.rmtree(wt_path)

        # Create worktree from the fetched PR branch
        # Use the remote ref to ensure we get the latest
        base_ref = f"origin/{head_branch}"

        # Check if the target branch already exists (pre-created by flow_dispatch).
        # If so, attach it to the worktree without -b (which would try to create it).
        branch_exists = self._branch_exists_locally(branch)

        try:
            if branch_exists:
                # Branch already exists (pre-created by flow_dispatch from
                # scene_base_ref) — reset it to the PR base before attaching.
                ref_result = subprocess.run(
                    ["git", "update-ref", f"refs/heads/{branch}", base_ref],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if ref_result.returncode != 0:
                    logger.bind(
                        issue=issue_number,
                        branch=branch,
                        pr_number=pr_number,
                        stderr=ref_result.stderr,
                    ).error("git update-ref failed, cannot reset branch to PR base")
                    return None
                cmd = ["git", "worktree", "add", str(wt_path), branch]
            else:
                # Create new branch from the PR base ref
                cmd = ["git", "worktree", "add", "-b", branch, str(wt_path), base_ref]

            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            logger.bind(
                issue=issue_number,
                branch=branch,
                pr_number=pr_number,
                error=str(exc),
            ).error("Failed to create worktree from PR branch")
            return None

        if result.returncode != 0:
            logger.bind(
                issue=issue_number,
                branch=branch,
                pr_number=pr_number,
                stderr=result.stderr,
            ).error("Git worktree add failed from PR branch")
            return None

        logger.info(
            "Created issue worktree from PR branch",
            issue=issue_number,
            branch=branch,
            pr_number=pr_number,
            source_branch=base_ref,
            path=str(wt_path),
        )
        initialize_worktree(self.repo_path, wt_path, reason="issue")

        return WorktreeContext(
            path=wt_path,
            is_temporary=False,
            branch=branch,
            issue_number=issue_number,
        )
