"""Cleanup executor for expired resources (worktrees, branches)."""

from loguru import logger

from vibe3.config import PeriodicCheckConfig
from vibe3.orchestra.logging import append_orchestra_event


async def execute_expired_resource_cleanup(
    config: PeriodicCheckConfig,
    tick_number: int,
) -> None:
    """Execute expired resource cleanup (worktrees, local/remote branches).

    This function is called from HeartbeatServer's tick loop when
    tick_number % interval_ticks == 0.

    Args:
        config: Cleanup configuration (enabled flags, max_age_days, etc.)
        tick_number: Current tick number (for logging)
    """
    # Delay imports to avoid circular dependencies
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.expired_resource_cleanup_service import (
        ExpiredResourceCleanupService,
    )

    # Initialize services
    store = SQLiteClient()
    git_client = GitClient()
    github_client: GitHubClient | None = None

    # Only initialize GitHub client if remote branch cleanup is enabled
    if config.enable_remote_branch_cleanup:
        try:
            github_client = GitHubClient()
        except Exception as exc:
            logger.bind(domain="orchestra", action="cleanup").warning(
                "Failed to initialize GitHub client, "
                f"skipping remote branch cleanup: {exc}"
            )

    service = ExpiredResourceCleanupService(
        store=store,
        git_client=git_client,
        github_client=github_client,
    )

    # Cleanup worktrees
    if config.enable_worktree_cleanup:
        try:
            result = service.clean_expired_agent_worktrees(
                config.max_age_days, quiet=True
            )
            cleaned = result.get("cleaned", [])
            if cleaned and isinstance(cleaned, list) and len(cleaned) > 0:
                append_orchestra_event(
                    "server",
                    (
                        f"tick #{tick_number} cleanup: cleaned "
                        f"{len(cleaned)} expired worktrees"
                    ),
                )
                logger.bind(domain="orchestra", action="cleanup").info(
                    f"Cleaned {len(cleaned)} expired worktrees"
                )
        except Exception as exc:
            append_orchestra_event(
                "server",
                f"tick #{tick_number} worktree cleanup failed: {exc}",
                level="WARNING",
            )
            logger.bind(domain="orchestra", action="cleanup").warning(
                f"Worktree cleanup failed: {exc}"
            )

    # Cleanup local branches
    if config.enable_local_branch_cleanup:
        try:
            result = service.clean_expired_local_branches(
                config.max_age_days, quiet=True
            )
            cleaned = result.get("cleaned", [])
            if cleaned and isinstance(cleaned, list) and len(cleaned) > 0:
                append_orchestra_event(
                    "server",
                    (
                        f"tick #{tick_number} cleanup: cleaned "
                        f"{len(cleaned)} expired local branches"
                    ),
                )
                logger.bind(domain="orchestra", action="cleanup").info(
                    f"Cleaned {len(cleaned)} expired local branches"
                )
        except Exception as exc:
            append_orchestra_event(
                "server",
                f"tick #{tick_number} local branch cleanup failed: {exc}",
                level="WARNING",
            )
            logger.bind(domain="orchestra", action="cleanup").warning(
                f"Local branch cleanup failed: {exc}"
            )

    # Cleanup remote branches (only if GitHub client available)
    if config.enable_remote_branch_cleanup and github_client is not None:
        try:
            result = service.clean_expired_remote_branches(
                config.max_age_days, quiet=True
            )
            cleaned = result.get("cleaned", [])
            if cleaned and isinstance(cleaned, list) and len(cleaned) > 0:
                append_orchestra_event(
                    "server",
                    (
                        f"tick #{tick_number} cleanup: cleaned "
                        f"{len(cleaned)} expired remote branches"
                    ),
                )
                logger.bind(domain="orchestra", action="cleanup").info(
                    f"Cleaned {len(cleaned)} expired remote branches"
                )
        except Exception as exc:
            append_orchestra_event(
                "server",
                f"tick #{tick_number} remote branch cleanup failed: {exc}",
                level="WARNING",
            )
            logger.bind(domain="orchestra", action="cleanup").warning(
                f"Remote branch cleanup failed: {exc}"
            )
