"""Shared utility functions subpackage.

This package provides cross-cutting utilities used by other service subpackages
and by external consumers (commands, execution, server).

Public API Contract:
- format_agent_actor, format_dry_run_header, extract_role_from_actor: Actor formatting
- ArtifactParser: Artifact parsing
- MissingTaskIssueError, build_bind_task_hint, ensure_task_issue_bound: Binding guard
- resolve_issue_branch_input: Branch resolution
- is_human_comment: Comment detection
- FlowContextCacheService: Context caching
- DependencyResolution, DependencyResolutionService: Dependency resolution
- log_dispatch_error, has_recent_specific_error: Error utilities
- emit_issue_failed, get_role_block_function: Flow execution helpers
- material_loader, policy_loader: File loading
- LabelService: Label management
- classify_dispatch_eligibility, get_highest_priority_state, get_state_labels,
  has_roadmap_label,
  has_manager_assignee, normalize_labels, ORCHESTRA_GOVERNED_LABEL,
  clean_old_state_labels, has_orchestra_governed, should_skip_from_queue,
  normalize_assignees: Label utilities
- LocService, LOCStats: LOC analysis
- GitPathProtocol, check_ref_exists, get_git_common_dir, get_worktree_root,
  ref_to_handoff_cmd, sanitize_event_detail_paths, resolve_ref_path:
  Path utilities
- SignatureService: Signature management
- SpecRefService: Spec reference management
- StatusQueryService, is_auto_task_branch, is_dev_collab_branch: Status query
- TIMELINE_DISPLAY_MAP, parse_timeline_from_comments: Timeline utilities
- VersionService: Version management

All other symbols are internal to the shared package and should be imported directly.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.shared.actors import (
        extract_role_from_actor,
        format_agent_actor,
        format_dry_run_header,
    )
    from vibe3.services.shared.artifacts import ArtifactParser
    from vibe3.services.shared.binding_guard import (
        MissingTaskIssueError,
        build_bind_task_hint,
        emit_issue_failed,
        ensure_task_issue_bound,
        get_role_block_function,
    )
    from vibe3.services.shared.branch_resolver import resolve_issue_branch_input
    from vibe3.services.shared.comment import is_human_comment
    from vibe3.services.shared.context_cache import FlowContextCacheService
    from vibe3.services.shared.dependency_resolution import (
        DependencyResolution,
        DependencyResolutionService,
    )
    from vibe3.services.shared.errors import (
        has_recent_specific_error,
        log_dispatch_error,
    )
    from vibe3.services.shared.file_loader import material_loader, policy_loader
    from vibe3.services.shared.label_service import LabelService
    from vibe3.services.shared.labels import (
        ORCHESTRA_GOVERNED_LABEL,
        classify_dispatch_eligibility,
        clean_old_state_labels,
        get_highest_priority_state,
        get_state_labels,
        has_manager_assignee,
        has_orchestra_governed,
        has_roadmap_label,
        normalize_assignees,
        normalize_labels,
        should_skip_from_queue,
    )
    from vibe3.services.shared.loc import LocService, LOCStats
    from vibe3.services.shared.paths import (
        GitPathProtocol,
        check_ref_exists,
        get_git_common_dir,
        get_worktree_root,
        ref_to_handoff_cmd,
        resolve_ref_path,
        sanitize_event_detail_paths,
    )
    from vibe3.services.shared.queue_dirty import (
        clear_queue_dirty,
        is_queue_dirty,
        mark_queue_dirty,
    )
    from vibe3.services.shared.signatures import SignatureService
    from vibe3.services.shared.spec_ref import SpecRefService
    from vibe3.services.shared.status_query import (
        StatusQueryService,
        is_auto_task_branch,
        is_dev_collab_branch,
    )
    from vibe3.services.shared.timeline import (
        TIMELINE_DISPLAY_MAP,
        parse_timeline_from_comments,
    )
    from vibe3.services.shared.versions import VersionService

__all__ = [
    "ArtifactParser",
    "DependencyResolution",
    "DependencyResolutionService",
    "FlowContextCacheService",
    "GitPathProtocol",
    "LabelService",
    "LOCStats",
    "LocService",
    "MissingTaskIssueError",
    "ORCHESTRA_GOVERNED_LABEL",
    "SignatureService",
    "SpecRefService",
    "StatusQueryService",
    "TIMELINE_DISPLAY_MAP",
    "VersionService",
    "build_bind_task_hint",
    "check_ref_exists",
    "classify_dispatch_eligibility",
    "clean_old_state_labels",
    "clear_queue_dirty",
    "emit_issue_failed",
    "ensure_task_issue_bound",
    "extract_role_from_actor",
    "format_agent_actor",
    "format_dry_run_header",
    "get_git_common_dir",
    "get_highest_priority_state",
    "get_role_block_function",
    "get_state_labels",
    "get_worktree_root",
    "has_manager_assignee",
    "has_orchestra_governed",
    "has_recent_specific_error",
    "has_roadmap_label",
    "is_auto_task_branch",
    "is_dev_collab_branch",
    "is_human_comment",
    "is_queue_dirty",
    "log_dispatch_error",
    "mark_queue_dirty",
    "material_loader",
    "normalize_assignees",
    "normalize_labels",
    "parse_timeline_from_comments",
    "policy_loader",
    "ref_to_handoff_cmd",
    "resolve_issue_branch_input",
    "resolve_ref_path",
    "sanitize_event_detail_paths",
    "should_skip_from_queue",
]

_SYMBOL_MODULES = {
    "ArtifactParser": "vibe3.services.shared.artifacts",
    "DependencyResolution": "vibe3.services.shared.dependency_resolution",
    "DependencyResolutionService": "vibe3.services.shared.dependency_resolution",
    "FlowContextCacheService": "vibe3.services.shared.context_cache",
    "GitPathProtocol": "vibe3.services.shared.paths",
    "LabelService": "vibe3.services.shared.label_service",
    "LOCStats": "vibe3.services.shared.loc",
    "LocService": "vibe3.services.shared.loc",
    "MissingTaskIssueError": "vibe3.services.shared.binding_guard",
    "ORCHESTRA_GOVERNED_LABEL": "vibe3.services.shared.labels",
    "SignatureService": "vibe3.services.shared.signatures",
    "SpecRefService": "vibe3.services.shared.spec_ref",
    "StatusQueryService": "vibe3.services.shared.status_query",
    "TIMELINE_DISPLAY_MAP": "vibe3.services.shared.timeline",
    "VersionService": "vibe3.services.shared.versions",
    "build_bind_task_hint": "vibe3.services.shared.binding_guard",
    "check_ref_exists": "vibe3.services.shared.paths",
    "classify_dispatch_eligibility": "vibe3.services.shared.labels",
    "clean_old_state_labels": "vibe3.services.shared.labels",
    "clear_queue_dirty": "vibe3.services.shared.queue_dirty",
    "emit_issue_failed": "vibe3.services.shared.binding_guard",
    "ensure_task_issue_bound": "vibe3.services.shared.binding_guard",
    "extract_role_from_actor": "vibe3.services.shared.actors",
    "format_agent_actor": "vibe3.services.shared.actors",
    "format_dry_run_header": "vibe3.services.shared.actors",
    "get_git_common_dir": "vibe3.services.shared.paths",
    "get_highest_priority_state": "vibe3.services.shared.labels",
    "get_role_block_function": "vibe3.services.shared.binding_guard",
    "get_state_labels": "vibe3.services.shared.labels",
    "get_worktree_root": "vibe3.services.shared.paths",
    "has_manager_assignee": "vibe3.services.shared.labels",
    "has_orchestra_governed": "vibe3.services.shared.labels",
    "has_recent_specific_error": "vibe3.services.shared.errors",
    "has_roadmap_label": "vibe3.services.shared.labels",
    "is_auto_task_branch": "vibe3.services.shared.status_query",
    "is_dev_collab_branch": "vibe3.services.shared.status_query",
    "is_human_comment": "vibe3.services.shared.comment",
    "is_queue_dirty": "vibe3.services.shared.queue_dirty",
    "log_dispatch_error": "vibe3.services.shared.errors",
    "mark_queue_dirty": "vibe3.services.shared.queue_dirty",
    "material_loader": "vibe3.services.shared.file_loader",
    "normalize_assignees": "vibe3.services.shared.labels",
    "normalize_labels": "vibe3.services.shared.labels",
    "parse_timeline_from_comments": "vibe3.services.shared.timeline",
    "policy_loader": "vibe3.services.shared.file_loader",
    "ref_to_handoff_cmd": "vibe3.services.shared.paths",
    "resolve_issue_branch_input": "vibe3.services.shared.branch_resolver",
    "resolve_ref_path": "vibe3.services.shared.paths",
    "sanitize_event_detail_paths": "vibe3.services.shared.paths",
    "should_skip_from_queue": "vibe3.services.shared.labels",
}

assert set(__all__) == set(_SYMBOL_MODULES.keys()), (
    "Mismatch between __all__ and _SYMBOL_MODULES:\n"
    f"  In __all__ only: {set(__all__) - set(_SYMBOL_MODULES)}\n"
    f"  In _SYMBOL_MODULES only: {set(_SYMBOL_MODULES.keys()) - set(__all__)}"
)


def __getattr__(name: str) -> Any:
    """Lazy import for Shared services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.shared import LabelService, has_recent_specific_error

    While avoiding circular imports at module load time.
    """
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
