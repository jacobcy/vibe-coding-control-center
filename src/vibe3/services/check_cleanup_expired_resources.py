"""Helpers for expired resource cleanup used by check cleanup service."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.git_worktree_ops import remove_worktree

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient


def clean_expired_agent_worktrees(
    store: "SQLiteClient", max_age_days: int = 7
) -> dict[str, object]:
    """Clean expired agent worktrees with live-session protection."""
    logger.bind(domain="check", action="clean_agent_worktrees").info(
        f"Checking agent worktrees older than {max_age_days} days"
    )

    base = Path(".claude/worktrees")
    if not base.exists():
        return {"cleaned": [], "skipped_live": [], "failed": []}

    cutoff = datetime.now() - timedelta(days=max_age_days)
    cleaned: list[str] = []
    skipped_live: list[str] = []
    failed: list[str] = []

    for worktree_dir in base.glob("agent-*"):
        if not worktree_dir.is_dir():
            continue

        worktree_name = worktree_dir.name
        try:
            if datetime.fromtimestamp(worktree_dir.stat().st_mtime) >= cutoff:
                continue

            live_sessions = store.list_live_sessions_by_worktree(
                str(worktree_dir.resolve())
            )
            if live_sessions:
                skipped_live.append(worktree_name)
                logger.bind(
                    domain="check",
                    worktree=worktree_name,
                    session_count=len(live_sessions),
                ).info("Skipped agent worktree with live runtime sessions")
                continue

            remove_worktree(worktree_dir, force=True)
            cleaned.append(worktree_name)
            logger.bind(domain="check", worktree=worktree_name).info(
                "Deleted expired agent worktree"
            )
        except Exception as exc:
            failed.append(f"{worktree_name}: {exc}")
            logger.bind(domain="check", worktree=worktree_name).warning(
                f"Failed to clean agent worktree: {exc}"
            )

    return {"cleaned": cleaned, "skipped_live": skipped_live, "failed": failed}


def clean_expired_remote_branches(
    git_client: "GitClient",
    github_client: "GitHubClient | None" = None,
    max_age_days: int = 7,
) -> dict[str, object]:
    """Clean expired remote branches after protected/open-PR checks."""
    logger.bind(domain="check", action="clean_remote_branches").info(
        f"Checking remote branches older than {max_age_days} days"
    )

    from vibe3.config.settings import VibeConfig

    protected = set(VibeConfig.get_defaults().flow.protected_branches)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cleaned: list[str] = []
    skipped_protected: list[str] = []
    skipped_pr: list[str] = []
    failed: list[str] = []

    try:
        remote_branches = git_client.get_all_branches_with_timestamps(remote=True)
    except Exception as exc:
        logger.bind(domain="check").error(f"Failed to get remote branches: {exc}")
        return _remote_cleanup_result(failed=[str(exc)])

    try:
        from vibe3.clients.github_client import GitHubClient

        gh = github_client or GitHubClient()
        pr_branches = {pr.head_branch for pr in gh.list_all_prs(state="open")}
    except Exception as exc:
        logger.bind(domain="check").error(f"Failed to get open PRs: {exc}")
        return _remote_cleanup_result(
            failed=["PR check failed - cannot safely proceed with cleanup"]
        )

    for branch_info in remote_branches:
        branch = branch_info["branch"]
        branch_name = branch.removeprefix("origin/")
        try:
            if branch_name in protected:
                skipped_protected.append(branch)
                continue
            if branch_name in pr_branches:
                skipped_pr.append(branch)
                logger.bind(domain="check", branch=branch).info(
                    "Skipped remote branch with open PR"
                )
                continue
            if _parse_git_timestamp(branch_info["timestamp"]) >= cutoff:
                continue

            git_client.delete_remote_branch(branch_name)
            cleaned.append(branch)
            logger.bind(domain="check", branch=branch).info(
                "Deleted expired remote branch"
            )
        except Exception as exc:
            failed.append(f"{branch}: {exc}")
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to clean remote branch: {exc}"
            )

    return _remote_cleanup_result(
        cleaned=cleaned,
        skipped_protected=skipped_protected,
        skipped_pr=skipped_pr,
        failed=failed,
    )


def clean_expired_local_branches(
    git_client: "GitClient",
    get_live_branches: Callable[[], set[str]],
    max_age_days: int = 7,
) -> dict[str, object]:
    """Clean expired local branches after branch/session/worktree checks."""
    logger.bind(domain="check", action="clean_local_branches").info(
        f"Checking local branches older than {max_age_days} days"
    )

    from vibe3.config.settings import VibeConfig

    protected = set(VibeConfig.get_defaults().flow.protected_branches)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cleaned: list[str] = []
    skipped_protected: list[str] = []
    skipped_current: list[str] = []
    skipped_live: list[str] = []
    skipped_worktree: list[str] = []
    failed: list[str] = []

    try:
        current_branch = git_client.get_current_branch()
    except Exception as exc:
        logger.bind(domain="check").error(f"Failed to get current branch: {exc}")
        return _local_cleanup_result(failed=[str(exc)])

    try:
        branches_with_live = get_live_branches()
    except SystemError:
        logger.bind(domain="check").error(
            "Failed to get live sessions, skipping local branch cleanup"
        )
        return _local_cleanup_result(failed=["live session query failed"])

    try:
        local_branches = git_client.get_all_branches_with_timestamps(remote=False)
    except Exception as exc:
        logger.bind(domain="check").error(f"Failed to get local branches: {exc}")
        return _local_cleanup_result(failed=[str(exc)])

    for branch_info in local_branches:
        branch = branch_info["branch"]
        try:
            if branch in protected:
                skipped_protected.append(branch)
                continue
            if branch == current_branch:
                skipped_current.append(branch)
                continue
            if branch in branches_with_live:
                skipped_live.append(branch)
                logger.bind(domain="check", branch=branch).info(
                    "Skipped local branch with live session"
                )
                continue
            if _parse_git_timestamp(branch_info["timestamp"]) >= cutoff:
                continue
            if not git_client.branch_exists(branch):
                continue

            if git_client.is_branch_occupied_by_worktree(branch):
                worktree_path = git_client.find_worktree_path_for_branch(branch)
                if worktree_path:
                    remove_worktree(Path(worktree_path), force=True)
                    skipped_worktree.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        f"Deleted worktree at {worktree_path}"
                    )

            git_client.delete_branch(branch, force=False)
            cleaned.append(branch)
            logger.bind(domain="check", branch=branch).info(
                "Deleted expired local branch"
            )
        except Exception as exc:
            failed.append(f"{branch}: {exc}")
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to clean local branch: {exc}"
            )

    return _local_cleanup_result(
        cleaned=cleaned,
        skipped_protected=skipped_protected,
        skipped_current=skipped_current,
        skipped_live=skipped_live,
        skipped_worktree=skipped_worktree,
        failed=failed,
    )


def _parse_git_timestamp(timestamp_str: str) -> datetime:
    normalized = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", timestamp_str.strip())
    return datetime.fromisoformat(normalized)


def _remote_cleanup_result(
    cleaned: list[str] | None = None,
    skipped_protected: list[str] | None = None,
    skipped_pr: list[str] | None = None,
    failed: list[str] | None = None,
) -> dict[str, object]:
    return {
        "cleaned": cleaned or [],
        "skipped_protected": skipped_protected or [],
        "skipped_pr": skipped_pr or [],
        "failed": failed or [],
    }


def _local_cleanup_result(
    cleaned: list[str] | None = None,
    skipped_protected: list[str] | None = None,
    skipped_current: list[str] | None = None,
    skipped_live: list[str] | None = None,
    skipped_worktree: list[str] | None = None,
    failed: list[str] | None = None,
) -> dict[str, object]:
    return {
        "cleaned": cleaned or [],
        "skipped_protected": skipped_protected or [],
        "skipped_current": skipped_current or [],
        "skipped_live": skipped_live or [],
        "skipped_worktree": skipped_worktree or [],
        "failed": failed or [],
    }
