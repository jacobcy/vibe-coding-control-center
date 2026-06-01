"""Expired resource cleanup service - handles cleanup of old worktrees and branches.

This service is separated from check_cleanup_service.py to keep responsibilities clear:
- check_cleanup_service.py: Terminal flow cleanup (done/aborted)
- expired_resource_cleanup_service.py: Expired resource cleanup
  (agent worktrees, remote/local branches)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, cast

from loguru import logger

from vibe3.clients.git_worktree_ops import remove_worktree
from vibe3.clients.protocols import GitHubClientProtocol

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.services.pr_service import PRService


class ExpiredResourceCleanupService:
    """Service for cleaning up expired resources.

    Handles cleanup of:
    - Agent worktrees older than max_age_days
    - Remote non-protected branches older than max_age_days
    - Local non-protected branches older than max_age_days
    """

    def __init__(
        self,
        store: "SQLiteClient",
        git_client: "GitClient",
        github_client: "GitHubClient | None" = None,
        pr_service: "PRService | None" = None,
    ) -> None:
        self.store = store
        self.git_client = git_client
        self._github_client = github_client
        self._pr_service = pr_service

    @property
    def pr_service(self) -> "PRService":
        """Lazy-initialized PR service."""
        if self._pr_service is None:
            from vibe3.services.pr_service import PRService

            self._pr_service = PRService(
                github_client=cast(GitHubClientProtocol | None, self._github_client),
                git_client=self.git_client,
                store=self.store,
            )
        return self._pr_service

    def clean_expired_agent_worktrees(
        self, max_age_days: int = 7, *, quiet: bool = False
    ) -> dict[str, object]:
        """Clean expired agent worktrees older than max_age_days.

        Safety checks:
        - Check if worktree path has live runtime sessions
        - Skip worktrees with active sessions to avoid disrupting running agents

        Uses git worktree remove (not just rmtree) to properly clean both
        the physical directory and the git worktree metadata.

        Args:
            max_age_days: Max age in days before cleanup (default: 7)
            quiet: If True, suppress terminal output (for daemon/heartbeat use)

        Returns:
            Dict with 'cleaned' list and 'skipped_live' list
        """
        import typer

        logger.bind(domain="check", action="clean_agent_worktrees").info(
            f"Checking agent worktrees older than {max_age_days} days"
        )
        if not quiet:
            typer.echo(
                f"  [dim]Checking agent worktrees older than {max_age_days} days...[/]"
            )

        base = self._get_agent_worktree_base()
        if not base.exists():
            return {"cleaned": [], "skipped_live": [], "failed": []}

        cutoff = datetime.now() - timedelta(days=max_age_days)

        cleaned: list[str] = []
        skipped_live: list[str] = []
        failed: list[str] = []

        # Scan agent-* worktrees
        for worktree_dir in base.glob("agent-*"):
            if not worktree_dir.is_dir():
                continue

            worktree_name = worktree_dir.name

            try:
                # Get last modified time
                mtime = datetime.fromtimestamp(worktree_dir.stat().st_mtime)

                # Check age
                if mtime >= cutoff:
                    continue

                # Check if worktree path has live runtime sessions.
                # Uses absolute path to match worktree_path stored in
                # runtime_session table (populated by vibe3 worktree creation).
                # Agent worktrees created by Claude Code won't have entries
                # in this table, so they'll be processed normally.
                worktree_abs = str(worktree_dir.resolve())
                live_sessions = self.store.list_live_sessions_by_worktree(worktree_abs)
                if live_sessions:
                    skipped_live.append(worktree_name)
                    logger.bind(
                        domain="check",
                        worktree=worktree_name,
                        session_count=len(live_sessions),
                    ).info("Skipped agent worktree with live runtime sessions")
                    if not quiet:
                        typer.echo(
                            f"    [cyan][skipped][/cyan] {worktree_name} "
                            f"[dim](has {len(live_sessions)} live sessions)[/]"
                        )
                    continue

                # Properly remove worktree: cleans git metadata AND directory
                if not quiet:
                    typer.echo(f"    [yellow][cleaning][/yellow] {worktree_name}...")
                remove_worktree(worktree_dir, force=True)
                cleaned.append(worktree_name)
                logger.bind(domain="check", worktree=worktree_name).info(
                    "Deleted expired agent worktree"
                )
                if not quiet:
                    typer.echo(f"    [green][cleaned][/green]  {worktree_name}")

            except Exception as exc:
                failed.append(f"{worktree_name}: {exc}")
                logger.bind(domain="check", worktree=worktree_name).warning(
                    f"Failed to clean agent worktree: {exc}"
                )
                if not quiet:
                    typer.echo(
                        f"    [red][failed][/red]   {worktree_name}: {exc}",
                        err=True,
                    )

        return {"cleaned": cleaned, "skipped_live": skipped_live, "failed": failed}

    def clean_expired_remote_branches(
        self, max_age_days: int = 7, *, quiet: bool = False
    ) -> dict[str, object]:
        """Clean expired remote non-protected branches older than max_age_days.

        Safety checks:
        - Exclude protected branches (main, master, develop)
        - Check for open PR (skip if has open PR)
        - Check branch age

        Args:
            max_age_days: Max age in days before cleanup (default: 7)
            quiet: If True, suppress terminal output (for daemon/heartbeat use)

        Returns:
            Dict with 'cleaned', 'skipped_protected', 'skipped_pr', 'failed' lists
        """
        import typer

        logger.bind(domain="check", action="clean_remote_branches").info(
            f"Checking remote branches older than {max_age_days} days"
        )
        if not quiet:
            typer.echo(
                f"  [dim]Checking remote branches older than {max_age_days} days...[/]"
            )

        # Load protected branches from config
        from vibe3.config.settings import VibeConfig

        config = VibeConfig.get_defaults()
        protected = set(config.flow.protected_branches)

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        cleaned: list[str] = []
        skipped_protected: list[str] = []
        skipped_pr: list[str] = []
        failed: list[str] = []

        # Get all remote branches with timestamps
        try:
            remote_branches = self.git_client.get_all_branches_with_timestamps(
                remote=True
            )
        except Exception as exc:
            logger.bind(domain="check").error(f"Failed to get remote branches: {exc}")
            if not quiet:
                typer.echo(
                    f"    [red][error][/red] Failed to get remote branches: {exc}",
                    err=True,
                )
            return {
                "cleaned": [],
                "skipped_protected": [],
                "skipped_pr": [],
                "failed": [str(exc)],
            }

        # Get open PRs via shared batch cache path
        try:
            pr_branches = set(self.pr_service.refresh_open_pr_cache())
        except Exception as exc:
            logger.bind(domain="check").error(f"Failed to get open PRs: {exc}")
            if not quiet:
                typer.echo(
                    f"    [red][error][/red] Failed to get open PRs: {exc}",
                    err=True,
                )
            return {
                "cleaned": [],
                "skipped_protected": [],
                "skipped_pr": [],
                "failed": ["PR check failed - cannot safely proceed with cleanup"],
            }

        # Process each branch
        for branch_info in remote_branches:
            branch = branch_info["branch"]
            timestamp_str = branch_info["timestamp"]

            try:
                # Parse timestamp from git "%(committerdate:iso8601)" format:
                # "YYYY-MM-DD HH:MM:SS +ZZZZ"
                timestamp = self._parse_git_iso8601_timestamp(timestamp_str)

                # Extract branch name (remove origin/ prefix)
                branch_name = branch.replace("origin/", "", 1)

                # Skip protected branches
                if branch_name in protected:
                    skipped_protected.append(branch)
                    continue

                # Skip if has open PR
                if branch_name in pr_branches:
                    skipped_pr.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        "Skipped remote branch with open PR"
                    )
                    if not quiet:
                        typer.echo(
                            f"    [cyan][skipped][/cyan] {branch} "
                            "[dim](has open PR)[/]"
                        )
                    continue

                # Check age
                if timestamp >= cutoff:
                    continue

                # Delete remote branch
                if not quiet:
                    typer.echo(f"    [yellow][cleaning][/yellow] {branch}...")
                self.git_client.delete_remote_branch(branch_name)
                cleaned.append(branch)
                logger.bind(domain="check", branch=branch).info(
                    "Deleted expired remote branch"
                )
                if not quiet:
                    typer.echo(f"    [green][cleaned][/green]  {branch}")

            except Exception as exc:
                failed.append(f"{branch}: {exc}")
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to clean remote branch: {exc}"
                )
                if not quiet:
                    typer.echo(f"    [red][failed][/red]   {branch}: {exc}", err=True)

        return {
            "cleaned": cleaned,
            "skipped_protected": skipped_protected,
            "skipped_pr": skipped_pr,
            "failed": failed,
        }

    def clean_expired_local_branches(
        self, max_age_days: int = 7, *, quiet: bool = False
    ) -> dict[str, object]:
        """Clean expired local non-protected branches older than max_age_days.

        Safety checks:
        - Exclude protected branches (main, master, develop)
        - Exclude current branch
        - Check for live session
        - Check for worktree occupation
        - Check branch age

        Args:
            max_age_days: Max age in days before cleanup (default: 7)
            quiet: If True, suppress terminal output (for daemon/heartbeat use)

        Returns:
            Dict with 'cleaned', 'skipped_protected', 'skipped_current',
            'skipped_live', 'skipped_worktree', 'failed' lists
        """
        import typer

        logger.bind(domain="check", action="clean_local_branches").info(
            f"Checking local branches older than {max_age_days} days"
        )
        if not quiet:
            typer.echo(
                f"  [dim]Checking local branches older than {max_age_days} days...[/]"
            )

        # Load protected branches from config
        from vibe3.config.settings import VibeConfig

        config = VibeConfig.get_defaults()
        protected = set(config.flow.protected_branches)

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        cleaned: list[str] = []
        skipped_protected: list[str] = []
        skipped_current: list[str] = []
        skipped_live: list[str] = []
        skipped_worktree: list[str] = []
        failed: list[str] = []

        # Get current branch
        try:
            current_branch = self.git_client.get_current_branch()
        except Exception as exc:
            logger.bind(domain="check").error(f"Failed to get current branch: {exc}")
            if not quiet:
                typer.echo(
                    f"    [red][error][/red] Failed to get current branch: {exc}",
                    err=True,
                )
            return {
                "cleaned": [],
                "skipped_protected": [],
                "skipped_current": [],
                "skipped_live": [],
                "skipped_worktree": [],
                "failed": [str(exc)],
            }

        # Get branches with live sessions
        try:
            branches_with_live = self._get_branches_with_live_sessions()
        except SystemError:
            logger.bind(domain="check").error(
                "Failed to get live sessions, skipping local branch cleanup"
            )
            if not quiet:
                typer.echo(
                    "    [red][error][/red] Live session query failed, skipping",
                    err=True,
                )
            return {
                "cleaned": [],
                "skipped_protected": [],
                "skipped_current": [],
                "skipped_live": [],
                "skipped_worktree": [],
                "failed": ["live session query failed"],
            }

        # Get all local branches with timestamps
        try:
            local_branches = self.git_client.get_all_branches_with_timestamps(
                remote=False
            )
        except Exception as exc:
            logger.bind(domain="check").error(f"Failed to get local branches: {exc}")
            if not quiet:
                typer.echo(
                    f"    [red][error][/red] Failed to get local branches: {exc}",
                    err=True,
                )
            return {
                "cleaned": [],
                "skipped_protected": [],
                "skipped_current": [],
                "skipped_live": [],
                "skipped_worktree": [],
                "failed": [str(exc)],
            }

        # Process each branch
        for branch_info in local_branches:
            branch = branch_info["branch"]
            timestamp_str = branch_info["timestamp"]

            try:
                # Parse timestamp from git "%(committerdate:iso8601)" format:
                # "YYYY-MM-DD HH:MM:SS +ZZZZ"
                timestamp = self._parse_git_iso8601_timestamp(timestamp_str)

                # Skip protected branches
                if branch in protected:
                    skipped_protected.append(branch)
                    continue

                # Skip current branch
                if branch == current_branch:
                    skipped_current.append(branch)
                    continue

                # Skip if has live session
                if branch in branches_with_live:
                    skipped_live.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        "Skipped local branch with live session"
                    )
                    if not quiet:
                        typer.echo(
                            f"    [cyan][skipped][/cyan] {branch} "
                            f"[dim](has live session)[/]"
                        )
                    continue

                # Check age
                if timestamp >= cutoff:
                    continue

                # Check if branch exists
                if not self.git_client.branch_exists(branch):
                    continue

                # Check if has worktree
                if self.git_client.is_branch_occupied_by_worktree(branch):
                    # Delete worktree first
                    worktree_path = self.git_client.find_worktree_path_for_branch(
                        branch
                    )
                    if worktree_path:
                        if not quiet:
                            typer.echo(
                                f"    [yellow][cleaning][/yellow] worktree for "
                                f"{branch} [dim]at {worktree_path}...[/]"
                            )
                        remove_worktree(worktree_path, force=True)
                        skipped_worktree.append(branch)
                        logger.bind(domain="check", branch=branch).info(
                            f"Deleted worktree at {worktree_path}"
                        )
                        if not quiet:
                            typer.echo(
                                f"    [green][cleaned][/green]  worktree for {branch}"
                            )

                # Delete local branch
                if not quiet:
                    typer.echo(f"    [yellow][cleaning][/yellow] {branch}...")
                self.git_client.delete_branch(branch, force=False)
                cleaned.append(branch)
                logger.bind(domain="check", branch=branch).info(
                    "Deleted expired local branch"
                )
                if not quiet:
                    typer.echo(f"    [green][cleaned][/green]  {branch}")

            except Exception as exc:
                failed.append(f"{branch}: {exc}")
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to clean local branch: {exc}"
                )
                if not quiet:
                    typer.echo(f"    [red][failed][/red]   {branch}: {exc}", err=True)

        return {
            "cleaned": cleaned,
            "skipped_protected": skipped_protected,
            "skipped_current": skipped_current,
            "skipped_live": skipped_live,
            "skipped_worktree": skipped_worktree,
            "failed": failed,
        }

    def _get_agent_worktree_base(self) -> Path:
        """Get agent worktree base directory (.claude/worktrees/)."""
        return Path(".claude/worktrees")

    @staticmethod
    def _parse_git_iso8601_timestamp(timestamp_str: str) -> datetime:
        """Parse git iso8601 timestamp from `%(committerdate:iso8601)` format."""
        return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S %z")

    def _get_branches_with_live_sessions(self) -> set[str]:
        """Batch query all live sessions and return branches with active sessions.

        This is a pre-filter optimization: instead of checking live sessions
        per branch during cleanup (N queries), we query once upfront and
        filter out branches with live sessions before cleanup attempts.

        Returns:
            Set of branch names that have truly live sessions.

        Raises:
            SystemError: If query fails, preventing accidental cleanup.
        """
        try:
            from vibe3.agents import CodeagentBackend
            from vibe3.environment.session_registry import SessionRegistryService

            backend = CodeagentBackend()
            registry = SessionRegistryService(store=self.store, backend=backend)

            # Reuse existing method: batch query + liveness verification
            return registry.get_all_branches_with_live_sessions()

        except Exception as exc:
            logger.bind(domain="check").error(
                f"Failed to query live sessions: {exc}. "
                "Cannot proceed with cleanup - manual verification required."
            )
            raise SystemError(
                f"Live session query failed: {exc}. "
                "Cleanup aborted to prevent accidental deletion of active sessions. "
                "Please verify manually or retry."
            ) from exc
