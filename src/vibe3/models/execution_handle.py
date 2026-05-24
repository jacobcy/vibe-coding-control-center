"""Execution handle models for async operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AsyncExecutionHandle:
    """Async execution metadata returned by the wrapper adapter."""

    tmux_session: str
    log_path: Path
    prompt_file_path: Path
