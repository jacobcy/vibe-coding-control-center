"""Backward compatibility — migrated to services.shared.paths."""

from vibe3.services.shared.paths import (  # noqa: F401
    GitClientProtocol,
    GitPathProtocol,
    _get_git_client,
    find_worktree_path_for_branch,
    get_git_common_dir,
    get_worktree_root,
)
