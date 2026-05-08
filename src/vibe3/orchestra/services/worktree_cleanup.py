"""WorktreeCleanupService: safe cleanup of temporary do/* worktrees."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import time

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.clients.git_worktree_ops import remove_worktree
from vibe3.exceptions import GitError
from vibe3.models.orchestra_config import OrchestraConfig, WorktreeCleanupConfig
from vibe3.runtime.service_protocol import GitHubEvent, ServiceBase


class CleanupDecision(Enum):
    """Decision for a worktree cleanup assessment."""

    CLEAN = "clean"
    SKIP_DIRTY = "skip_dirty"
    SKIP_ACTIVE_SESSION = "skip_active_session"
    SKIP_TTL_NOT_EXPIRED = "skip_ttl_not_expired"
    SKIP_NOT_DO_PATTERN = "skip_not_do_pattern"


@dataclass
class WorktreeInfo:
    """Information about a worktree."""

    path: Path
    branch: str
    mtime: float  # modification time as timestamp


@dataclass
class CleanupResult:
    """Result of a worktree cleanup attempt."""

    path: Path
    success: bool
    reason: str


def list_do_worktrees(repo_path: Path) -> list[WorktreeInfo]:
    """List all do/* worktrees for the repository.

    Parses `git worktree list --porcelain` output and filters to worktrees
    whose directory name matches the do-* pattern (e.g., do-20260430-abc123).

    Args:
        repo_path: Path to the main repository.

    Returns:
        List of WorktreeInfo for matching worktrees.
    """
    try:
        git_client = GitClient()
        worktree_entries = git_client.list_worktrees(cwd=repo_path)
    except Exception as exc:
        logger.bind(domain="orchestra").warning(
            "Exception listing worktrees", error=str(exc)
        )
        return []

    worktrees: list[WorktreeInfo] = []
    for wt_path, wt_branch in worktree_entries:
        path = Path(wt_path)
        # Check if directory name matches do-* pattern
        if path.name.startswith("do-"):
            try:
                stat = path.stat()
                worktrees.append(
                    WorktreeInfo(
                        path=path,
                        branch=wt_branch,
                        mtime=stat.st_mtime,
                    )
                )
            except Exception as exc:
                logger.bind(domain="orchestra").debug(
                    "Failed to stat worktree path",
                    path=str(path),
                    error=str(exc),
                )

    return worktrees


def assess_worktree(wt: WorktreeInfo, config: WorktreeCleanupConfig) -> CleanupDecision:
    """Assess whether a worktree should be cleaned.

    Safety checks (in order):
    1. Pattern guard: Must match do-* naming
    2. Dirty check: No uncommitted changes
    3. Tmux session check: No active tmux session
    4. TTL check: Past TTL threshold

    Args:
        wt: Worktree information.
        config: Cleanup configuration.

    Returns:
        CleanupDecision indicating whether to clean or skip.
    """
    # 1. Pattern guard (should already be filtered, but double-check)
    if not wt.path.name.startswith("do-"):
        return CleanupDecision.SKIP_NOT_DO_PATTERN

    # 2. Dirty check
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=wt.path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return CleanupDecision.SKIP_DIRTY
    except Exception:
        pass

    # 3. Tmux session check
    if _has_active_tmux_session(wt.path):
        return CleanupDecision.SKIP_ACTIVE_SESSION

    # 4. TTL check
    current_time = time()
    age_seconds = current_time - wt.mtime
    ttl_seconds = config.ttl_hours * 3600

    if age_seconds < ttl_seconds:
        return CleanupDecision.SKIP_TTL_NOT_EXPIRED

    return CleanupDecision.CLEAN


def _has_active_tmux_session(wt_path: Path) -> bool:
    """Check if any tmux session path matches the worktree path.

    Args:
        wt_path: Worktree path to check

    Returns:
        True if an active tmux session is found for this worktree
    """
    try:
        sessions = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_path}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if sessions.returncode == 0:
            for line in sessions.stdout.strip().split("\n"):
                if not line:
                    continue
                if ":" in line:
                    session_name, session_path = line.split(":", 1)
                    if str(wt_path) in session_path or session_path.startswith(
                        str(wt_path)
                    ):
                        return True
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return False


def execute_cleanup(
    worktrees: list[WorktreeInfo], dry_run: bool, repo_path: Path
) -> list[CleanupResult]:
    """Execute cleanup for a list of worktrees.

    Args:
        worktrees: List of worktrees to clean.
        dry_run: If True, log decisions without removing.
        repo_path: Path to the main repository.

    Returns:
        List of CleanupResult for each worktree.
    """
    results: list[CleanupResult] = []

    for wt in worktrees:
        if dry_run:
            logger.bind(domain="orchestra").info(
                "Dry run: would clean worktree", path=str(wt.path)
            )
            results.append(CleanupResult(path=wt.path, success=True, reason="dry_run"))
            continue

        # Actual cleanup
        try:
            # Step 1: git worktree remove --force
            remove_worktree(wt.path, force=True)
            logger.bind(domain="orchestra").info(
                "Removed worktree via git", path=str(wt.path)
            )
            results.append(
                CleanupResult(path=wt.path, success=True, reason="git_remove")
            )
            # Step 2: git worktree prune (best-effort)
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            continue
        except GitError as exc:
            logger.bind(domain="orchestra").warning(
                "git worktree remove failed", path=str(wt.path), error=str(exc)
            )

        # Step 3: Fallback to rmtree if directory still exists
        if wt.path.exists():
            try:
                shutil.rmtree(wt.path)
                logger.bind(domain="orchestra").info(
                    "Forcefully removed worktree directory", path=str(wt.path)
                )
                results.append(
                    CleanupResult(path=wt.path, success=True, reason="rmtree_fallback")
                )
            except Exception as exc:
                logger.bind(domain="orchestra").error(
                    "Failed to remove worktree directory",
                    path=str(wt.path),
                    error=str(exc),
                )
                results.append(
                    CleanupResult(path=wt.path, success=False, reason=str(exc))
                )
        else:
            results.append(
                CleanupResult(path=wt.path, success=True, reason="already_gone")
            )

    return results


def find_worktrees_for_pr_branch(
    repo_path: Path, pr_head_branch: str
) -> list[WorktreeInfo]:
    """Find all do/* worktrees whose checked-out branch matches the PR's head branch.

    Args:
        repo_path: Path to the main repository.
        pr_head_branch: The PR's head branch name.

    Returns:
        List of matching WorktreeInfo.
    """
    all_worktrees = list_do_worktrees(repo_path)
    return [wt for wt in all_worktrees if wt.branch == pr_head_branch]


class WorktreeCleanupService(ServiceBase):
    """Service for cleaning up temporary do/* worktrees.

    Handles two triggers:
    1. Webhook-driven cleanup on PR close/merge
    2. Periodic TTL-based GC on heartbeat ticks
    """

    event_types = ["pull_request"]

    def __init__(self, config: OrchestraConfig, repo_path: Path | None = None):
        self.config = config
        self._repo_path = repo_path or Path.cwd()
        self._tick_counter = 0

    async def handle_event(self, event: GitHubEvent) -> None:
        """Handle pull_request closed/merged events."""
        if not self.config.cleanup.enabled:
            return
        if not self.config.cleanup.on_pr_closed:
            return
        if event.action != "closed":
            return

        pr_payload = event.payload.get("pull_request", {})
        head_ref = pr_payload.get("head", {}).get("ref", "")

        if not head_ref:
            return

        log = logger.bind(domain="orchestra", branch=head_ref)
        log.info("PR closed, checking for worktrees to clean")

        candidates = find_worktrees_for_pr_branch(self._repo_path, head_ref)
        if not candidates:
            log.debug("No matching worktrees found")
            return

        results = execute_cleanup(
            candidates, dry_run=self.config.cleanup.dry_run, repo_path=self._repo_path
        )

        # Log summary
        cleaned = sum(1 for r in results if r.success)
        log.info(
            "PR-triggered cleanup complete",
            worktrees_found=len(candidates),
            worktrees_cleaned=cleaned,
            dry_run=self.config.cleanup.dry_run,
        )

    async def on_tick(self) -> None:
        """Periodic TTL-based GC."""
        if not self.config.cleanup.enabled:
            return

        self._tick_counter += 1
        # Run TTL GC every 4 ticks (~1 hour at default interval)
        if self._tick_counter % 4 != 0:
            return

        log = logger.bind(domain="orchestra")
        log.debug("Running TTL-based worktree GC")

        candidates = list_do_worktrees(self._repo_path)
        if not candidates:
            return

        decisions = [assess_worktree(wt, self.config.cleanup) for wt in candidates]
        expired = [
            wt for wt, d in zip(candidates, decisions) if d == CleanupDecision.CLEAN
        ]
        skipped = [
            (wt, d)
            for wt, d in zip(candidates, decisions)
            if d != CleanupDecision.CLEAN
        ]

        # Log skip reasons
        for wt, reason in skipped:
            log.info(f"Skip worktree {wt.path}: {reason.value}")

        if not expired:
            return

        results = execute_cleanup(
            expired, dry_run=self.config.cleanup.dry_run, repo_path=self._repo_path
        )

        # Log summary
        cleaned = sum(1 for r in results if r.success)
        log.info(
            "TTL-based GC complete",
            worktrees_scanned=len(candidates),
            worktrees_expired=len(expired),
            worktrees_cleaned=cleaned,
            dry_run=self.config.cleanup.dry_run,
        )
