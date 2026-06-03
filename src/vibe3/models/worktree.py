"""Worktree requirement types for role execution."""

from enum import Enum


class WorktreeRequirement(str, Enum):
    """Worktree requirement for a role execution."""

    NONE = "none"  # No worktree needed (governance)
    PERMANENT = "permanent"  # Permanent worktree (manager)
    TEMPORARY = "temporary"  # Temporary worktree (supervisor apply)
