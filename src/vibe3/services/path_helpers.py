"""Backward compatibility — migrated to services.shared.paths."""

# Re-export handoff_resolution symbols for backward compatibility
# (these were imported and re-exported in the original path_helpers.py)
from vibe3.services.handoff_resolution import (  # noqa: F401
    _SHARED_HANDOFF_PREFIX,
    resolve_handoff_target,
)
from vibe3.services.shared.paths import (  # noqa: F401
    GitClientProtocol,
    check_ref_exists,
    get_git_common_dir,
    get_worktree_root,
    normalize_ref_path,
    ref_to_handoff_cmd,
    resolve_ref_path,
    sanitize_event_detail_paths,
)
