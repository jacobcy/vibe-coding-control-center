"""Observability module for orchestra event logging."""

from __future__ import annotations

import atexit
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import IO


def orchestra_log_dir(repo_root: Path | None = None) -> Path:
    override_dir = os.environ.get("VIBE3_ASYNC_LOG_DIR", "").strip()
    if override_dir:
        path = Path(override_dir).expanduser().resolve() / "orchestra"
    else:
        from vibe3.utils import find_repo_root

        root = repo_root or find_repo_root()
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


# ANSI color codes for terminal event highlighting
_COLOR_MAP: dict[str, str] = {
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "blue": "\033[34m",
    "gray": "\033[90m",
    "red_bold": "\033[1;31m",
}
_COLOR_RESET = "\033[0m"


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
    color: str | None = None,
) -> Path:
    """Append an event to the orchestra events log.

    Levels: DEBUG, INFO, WARNING, ERROR
    Default is INFO. Use VIBE3_ORCHESTRA_LOG_LEVEL to filter (default: INFO).

    Uses a module-level persistent file handle to avoid FD exhaustion
    from repeated open/close on every heartbeat tick.

    Args:
        component: Component name (e.g., 'dispatcher', 'server')
        message: Event message
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        repo_root: Optional repository root path
        color: Optional color name for ANSI highlighting (green, yellow, red, etc.)
               Only applied when stdout is a TTY (terminal environment)

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

    # Apply ANSI color if requested and stdout is a TTY
    if color is not None and sys.stdout.isatty() and color in _COLOR_MAP:
        color_code = _COLOR_MAP[color]
        if not message:
            handle.write("\n")
        else:
            handle.write(
                f"{color_code}[{timestamp}] [{component}] {message}{_COLOR_RESET}\n"
            )
    else:
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


def append_governance_event(
    message: str, *, repo_root: Path | None = None, color: str | None = None
) -> Path:
    """Append a governance event to both governance.log and events.log.

    Uses append mode and delegates to append_orchestra_event for events.log
    to benefit from persistent file handle.

    Args:
        message: Governance event message
        repo_root: Optional repository root path
        color: Optional color for events.log (governance.log remains plain text)

    Returns:
        Path to the governance.log file
    """
    path = governance_events_log_path(repo_root)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")
    # Delegate to append_orchestra_event to use persistent handle
    append_orchestra_event("governance", message, repo_root=repo_root, color=color)
    return path


def write_prompt_provenance(
    provenance: object,  # PromptRenderProvenance (avoid circular import)
    role: str,
    issue_number: int | None = None,
    repo_root: Path | None = None,
) -> Path:
    """Write PromptRenderProvenance as JSON artifact in dry-run directory.

    Args:
        provenance: PromptRenderProvenance model instance
        role: Role identifier (e.g., 'planner', 'governance')
        issue_number: Optional issue number for context
        repo_root: Optional repository root path

    Returns:
        Path to the written JSON file
    """
    from pydantic import BaseModel

    # Ensure we have a Pydantic model
    if not isinstance(provenance, BaseModel):
        raise TypeError("provenance must be a Pydantic BaseModel instance")

    # Generate filename with timestamp and optional issue number
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    issue_suffix = f"_{issue_number}" if issue_number else ""
    filename = f"provenance_{role}_{timestamp}{issue_suffix}.json"

    # Write to governance dry-run directory
    dry_run_path = governance_dry_run_dir(repo_root)
    output_path = dry_run_path / filename

    # Write JSON with model_dump()
    output_path.write_text(provenance.model_dump_json(indent=2), encoding="utf-8")

    return output_path
