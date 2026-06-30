"""Environment isolation modules (worktree, session, runtime assets)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.environment.session_naming import get_manager_session_name
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.environment.worktree import WorktreeManager
    from vibe3.environment.worktree_context import WorktreeContext
    from vibe3.environment.worktree_support import (
        find_worktree_by_path,
        find_worktree_for_branch,
    )

# Lazy imports
_LAZY_IMPORTS = {
    "SessionRegistryService": "vibe3.environment.session_registry",
    "WorktreeManager": "vibe3.environment.worktree",
    "WorktreeContext": "vibe3.environment.worktree_context",
    "find_worktree_by_path": "vibe3.environment.worktree_support",
    "find_worktree_for_branch": "vibe3.environment.worktree_support",
    "get_manager_session_name": "vibe3.environment.session_naming",
}


def __getattr__(name: str) -> object:
    """Lazy import for environment symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SessionRegistryService",
    "WorktreeManager",
    "WorktreeContext",
    "find_worktree_by_path",
    "find_worktree_for_branch",
    "get_manager_session_name",
]
