"""Shared utility functions subpackage."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.shared.branches import (
        resolve_branch_and_issue,
        resolve_branch_arg,
    )
    from vibe3.services.shared.errors import (
        has_recent_specific_error,
        record_dispatch_failure_if_unexpected,
        record_error,
    )
    from vibe3.services.shared.labels import (
        audit_multiple_state_labels,
        audit_orphan_execution_state,
        audit_orphan_orchestra_governed,
        audit_roadmap_state_conflict,
        clean_old_state_labels,
        normalize_assignees,
        normalize_labels,
        should_skip_from_queue,
    )
    from vibe3.services.shared.paths import (
        GitClientProtocol,
        check_ref_exists,
        find_worktree_path_for_branch,
        get_git_common_dir,
        get_worktree_root,
        normalize_ref_path,
        ref_to_handoff_cmd,
        resolve_ref_path,
        sanitize_event_detail_paths,
    )

__all__ = [
    # paths
    "GitClientProtocol",
    "check_ref_exists",
    "find_worktree_path_for_branch",
    "get_git_common_dir",
    "get_worktree_root",
    "normalize_ref_path",
    "ref_to_handoff_cmd",
    "resolve_ref_path",
    "sanitize_event_detail_paths",
    # errors
    "has_recent_specific_error",
    "record_dispatch_failure_if_unexpected",
    "record_error",
    # labels
    "audit_multiple_state_labels",
    "audit_orphan_execution_state",
    "audit_orphan_orchestra_governed",
    "audit_roadmap_state_conflict",
    "clean_old_state_labels",
    "normalize_assignees",
    "normalize_labels",
    "should_skip_from_queue",
    # branches
    "resolve_branch_and_issue",
    "resolve_branch_arg",
]

_SYMBOL_MODULES = {
    "GitClientProtocol": "vibe3.services.shared.paths",
    "check_ref_exists": "vibe3.services.shared.paths",
    "find_worktree_path_for_branch": "vibe3.services.shared.paths",
    "get_git_common_dir": "vibe3.services.shared.paths",
    "get_worktree_root": "vibe3.services.shared.paths",
    "normalize_ref_path": "vibe3.services.shared.paths",
    "ref_to_handoff_cmd": "vibe3.services.shared.paths",
    "resolve_ref_path": "vibe3.services.shared.paths",
    "sanitize_event_detail_paths": "vibe3.services.shared.paths",
    "has_recent_specific_error": "vibe3.services.shared.errors",
    "record_dispatch_failure_if_unexpected": "vibe3.services.shared.errors",
    "record_error": "vibe3.services.shared.errors",
    "audit_multiple_state_labels": "vibe3.services.shared.labels",
    "audit_orphan_execution_state": "vibe3.services.shared.labels",
    "audit_orphan_orchestra_governed": "vibe3.services.shared.labels",
    "audit_roadmap_state_conflict": "vibe3.services.shared.labels",
    "clean_old_state_labels": "vibe3.services.shared.labels",
    "normalize_assignees": "vibe3.services.shared.labels",
    "normalize_labels": "vibe3.services.shared.labels",
    "should_skip_from_queue": "vibe3.services.shared.labels",
    "resolve_branch_and_issue": "vibe3.services.shared.branches",
    "resolve_branch_arg": "vibe3.services.shared.branches",
}


def __getattr__(name: str) -> Any:
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        globals()[name] = symbol
        return symbol
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
