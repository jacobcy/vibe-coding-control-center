"""Shared worktree context types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class WorktreeContext:
    """Context for a git worktree resource."""

    path: Path
    is_temporary: bool
    branch: Optional[str] = None
    issue_number: Optional[int] = None
