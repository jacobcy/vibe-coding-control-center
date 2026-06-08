"""Cleanup executor for expired resources (worktrees, branches)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.config import PeriodicCheckConfig
from vibe3.observability import append_orchestra_event

if TYPE_CHECKING:
    from vibe3.orchestra import CleanupServiceProtocol


async def execute_expired_resource_cleanup(
    config: PeriodicCheckConfig,
    tick_number: int,
    cleanup_service: CleanupServiceProtocol | None = None,
) -> None:
    """Execute expired resource cleanup (worktrees, local/remote branches).

    Args:
        config: Cleanup configuration
        tick_number: Current tick number (for logging)
        cleanup_service: Injected cleanup service (optional, created if None)
    """
    if cleanup_service is None:
        import importlib

        _clients = importlib.import_module("vibe3.clients")
        _services = importlib.import_module("vibe3.services")

        store = _clients.SQLiteClient()
        git_client = _clients.GitClient()
        github_client = None

        if config.enable_remote_branch_cleanup:
            try:
                github_client = _clients.GitHubClient()
            except Exception as exc:
                logger.bind(domain="orchestra", action="cleanup").warning(
                    "Failed to initialize GitHub client, "
                    f"skipping remote branch cleanup: {exc}"
                )

        cleanup_service = _services.ExpiredResourceCleanupService(
            store=store,
            git_client=git_client,
            github_client=github_client,
        )

    service = cleanup_service

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
