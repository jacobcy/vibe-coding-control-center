"""Filesystem-backed orchestration logs."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def _repo_root() -> Path:
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


def append_orchestra_event(
    component: str,
    message: str,
    *,
    repo_root: Path | None = None,
) -> Path:
    if os.environ.get("VIBE3_ORCHESTRA_EVENT_LOG") != "1":
        return orchestra_events_log_path(repo_root)
    path = orchestra_events_log_path(repo_root)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] [{component}] {message}\n")
    return path


def append_orchestra_run_separator(
    *,
    repo_root: Path | None = None,
    title: str = "server run start",
) -> Path:
    """Append a run separator to events.log, preserving history.

    Uses append mode to keep previous runs instead of overwriting.
    """
    if os.environ.get("VIBE3_ORCHESTRA_EVENT_LOG") != "1":
        return orchestra_events_log_path(repo_root)
    path = orchestra_events_log_path(repo_root)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n========== {title} @ {timestamp} ==========\n")
    return path


def append_governance_event(message: str, *, repo_root: Path | None = None) -> Path:
    if os.environ.get("VIBE3_ORCHESTRA_EVENT_LOG") != "1":
        return governance_events_log_path(repo_root)
    path = governance_events_log_path(repo_root)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")
    append_orchestra_event("governance", message, repo_root=repo_root)
    return path
