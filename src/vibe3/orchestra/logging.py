"""Filesystem-backed orchestration logs."""

from __future__ import annotations

import atexit
import os
from datetime import datetime
from pathlib import Path
from typing import IO


def _repo_root() -> Path:
    """Get the main repository root directory.

    Uses git common dir to correctly handle worktrees:
    - In worktrees, git common dir points to the main repo's .git directory
    - In main repo, it points to the local .git directory
    - The parent of git common dir is always the main repository root

    Falls back to path-based detection if git command fails.
    """
    try:
        import subprocess

        # Get the shared .git directory (works in both main repo and worktrees)
        result = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_common_dir = Path(result.stdout.strip())
        # The parent of .git is the main repository root
        return git_common_dir.parent
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        # Fallback to path-based detection for non-git environments
        return Path(__file__).resolve().parents[3]


def orchestra_log_dir(repo_root: Path | None = None) -> Path:
    override_dir = os.environ.get("VIBE3_ASYNC_LOG_DIR", "").strip()
    if override_dir:
        path = Path(override_dir).expanduser().resolve() / "orchestra"
    else:
        root = repo_root or _repo_root()
        path = root / "temp" / "logs" / "orchestra"
    path.mkdir(parents=True, exist_ok=True)
    return path


def orchestra_events_log_path(repo_root: Path | None = None) -> Path:
    return orchestra_log_dir(repo_root) / "events.log"


def governance_log_dir(repo_root: Path | None = None) -> Path:
    path = orchestra_log_dir(repo_root) / "governance"
    path.mkdir(parents=True, exist_ok=True)
    return path


def governance_events_log_path(repo_root: Path | None = None) -> Path:
    return governance_log_dir(repo_root) / "governance.log"


def governance_dry_run_dir(repo_root: Path | None = None) -> Path:
    path = governance_log_dir(repo_root) / "dry-run"
    path.mkdir(parents=True, exist_ok=True)
    return path


# Module-level persistent file handle for events.log
# Avoids opening/closing on every tick, preventing FD exhaustion
_events_handle: IO[str] | None = None
_events_path: Path | None = None  # Track current log path to detect repo_root changes


def _open_events_log(repo_root: Path | None = None) -> tuple[IO[str], Path]:
    """Open events.log in append mode, creating parent dirs if needed.

    Returns:
        Tuple of (file handle, resolved path) to enable path tracking
    """
    path = orchestra_events_log_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a", encoding="utf-8")
    return handle, path


def _close_events_log() -> None:
    """Close the persistent events log handle."""
    global _events_handle, _events_path
    if _events_handle is not None:
        try:
            _events_handle.close()
        except Exception:
            pass
        _events_handle = None
        _events_path = None


atexit.register(_close_events_log)


def _ensure_events_handle(repo_root: Path | None = None) -> IO[str]:
    """Ensure the persistent events handle is open and pointing at the right path."""
    global _events_handle, _events_path
    target_path = orchestra_events_log_path(repo_root)
    if _events_handle is None or _events_path != target_path:
        if _events_handle is not None:
            try:
                _events_handle.close()
            except Exception:
                pass
        _events_handle, _events_path = _open_events_log(repo_root)
    return _events_handle


def append_orchestra_event(
    component: str,
    message: str,
    *,
    level: str = "INFO",
    repo_root: Path | None = None,
) -> Path:
    """Append an event to the orchestra events log.

    Levels: DEBUG, INFO, WARNING, ERROR
    Default is INFO. Use VIBE3_ORCHESTRA_LOG_LEVEL to filter (default: INFO).

    Uses a module-level persistent file handle to avoid FD exhaustion
    from repeated open/close on every heartbeat tick.

    Returns:
        Path to the events.log file (consistent return type)
    """
    if os.environ.get("VIBE3_ORCHESTRA_EVENT_LOG") != "1":
        return orchestra_events_log_path(repo_root)

    # Check log level filter (no I/O for filtered-out events)
    current_level = os.environ.get("VIBE3_ORCHESTRA_LOG_LEVEL", "INFO").upper()
    levels = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
    if levels.get(level.upper(), 1) < levels.get(current_level, 1):
        return orchestra_events_log_path(repo_root)

    handle = _ensure_events_handle(repo_root)
    timestamp = datetime.now().isoformat(timespec="seconds")
    if not message:
        handle.write("\n")
    else:
        handle.write(f"[{timestamp}] [{component}] {message}\n")
    handle.flush()
    assert _events_path is not None
    return _events_path


def append_orchestra_run_separator(
    *,
    repo_root: Path | None = None,
    title: str = "server run start",
) -> Path:
    """Append a run separator to events.log, preserving history.

    Uses append mode to keep previous runs instead of overwriting.
    Uses the persistent file handle to avoid FD exhaustion.

    Returns:
        Path to the events.log file (consistent return type)
    """
    if os.environ.get("VIBE3_ORCHESTRA_EVENT_LOG") != "1":
        return orchestra_events_log_path(repo_root)

    handle = _ensure_events_handle(repo_root)
    timestamp = datetime.now().isoformat(timespec="seconds")
    handle.write(f"\n========== {title} @ {timestamp} ==========\n")
    handle.flush()
    assert _events_path is not None
    return _events_path


def append_governance_event(message: str, *, repo_root: Path | None = None) -> Path:
    """Append a governance event to both governance.log and events.log.

    Uses append mode and delegates to append_orchestra_event for events.log
    to benefit from persistent file handle.
    """
    path = governance_events_log_path(repo_root)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")
    # Delegate to append_orchestra_event to use persistent handle
    append_orchestra_event("governance", message, repo_root=repo_root)
    return path
