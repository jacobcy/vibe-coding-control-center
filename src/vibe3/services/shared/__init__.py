"""Shared utility functions subpackage."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.shared.actors import (
        extract_role_from_actor,
        format_agent_actor,
        resolve_actor_backend_model,
    )
    from vibe3.services.shared.artifacts import ArtifactParser
    from vibe3.services.shared.branches import (
        resolve_branch_and_issue,
        resolve_branch_arg,
    )
    from vibe3.services.shared.errors import (
        has_recent_specific_error,
        record_dispatch_failure_if_unexpected,
        record_error,
    )
    from vibe3.services.shared.events import emit_issue_failed
    from vibe3.services.shared.label_anomalies import (
        LabelAnomaly,
        collect_label_anomalies,
    )
    from vibe3.services.shared.label_service import LabelService
    from vibe3.services.shared.labels import (
        ORCHESTRA_GOVERNED_LABEL,
        classify_dispatch_eligibility,
        clean_old_state_labels,
        get_conflicting_states,
        get_highest_priority_state,
        get_state_labels,
        has_execution_state,
        has_manager_assignee,
        has_orchestra_governed,
        has_roadmap_conflict,
        has_roadmap_label,
        normalize_assignees,
        normalize_labels,
        should_skip_from_queue,
    )
    from vibe3.services.shared.loc import LocService, LOCStats
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
    from vibe3.services.shared.roles import get_role_block_function
    from vibe3.services.shared.signatures import (
        AI_ASSISTANT_ACTORS,
        WORKFLOW_ACTOR,
        SignatureService,
    )
    from vibe3.services.shared.timeline import parse_timeline_from_comments
    from vibe3.services.shared.versions import VersionService

__all__ = [
    # actors
    "resolve_actor_backend_model",
    "format_agent_actor",
    "extract_role_from_actor",
    # artifacts
    "ArtifactParser",
    # events
    "emit_issue_failed",
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
    "LabelAnomaly",
    "LabelService",
    "classify_dispatch_eligibility",
    "clean_old_state_labels",
    "collect_label_anomalies",
    "get_conflicting_states",
    "get_highest_priority_state",
    "get_state_labels",
    "has_execution_state",
    "has_manager_assignee",
    "has_orchestra_governed",
    "has_roadmap_conflict",
    "has_roadmap_label",
    "normalize_assignees",
    "normalize_labels",
    "ORCHESTRA_GOVERNED_LABEL",
    "should_skip_from_queue",
    # loc
    "LOCStats",
    "LocService",
    # branches
    "resolve_branch_and_issue",
    "resolve_branch_arg",
    # roles
    "get_role_block_function",
    # signatures
    "AI_ASSISTANT_ACTORS",
    "WORKFLOW_ACTOR",
    "SignatureService",
    # timeline
    "parse_timeline_from_comments",
    # versions
    "VersionService",
]

_SYMBOL_MODULES = {
    # actors
    "resolve_actor_backend_model": "vibe3.services.shared.actors",
    "format_agent_actor": "vibe3.services.shared.actors",
    "extract_role_from_actor": "vibe3.services.shared.actors",
    # artifacts
    "ArtifactParser": "vibe3.services.shared.artifacts",
    # events
    "emit_issue_failed": "vibe3.services.shared.events",
    # paths
    "GitClientProtocol": "vibe3.services.shared.paths",
    "check_ref_exists": "vibe3.services.shared.paths",
    "find_worktree_path_for_branch": "vibe3.services.shared.paths",
    "get_git_common_dir": "vibe3.services.shared.paths",
    "get_worktree_root": "vibe3.services.shared.paths",
    "normalize_ref_path": "vibe3.services.shared.paths",
    "ref_to_handoff_cmd": "vibe3.services.shared.paths",
    "resolve_ref_path": "vibe3.services.shared.paths",
    "sanitize_event_detail_paths": "vibe3.services.shared.paths",
    # errors
    "has_recent_specific_error": "vibe3.services.shared.errors",
    "record_dispatch_failure_if_unexpected": "vibe3.services.shared.errors",
    "record_error": "vibe3.services.shared.errors",
    # labels
    "LabelAnomaly": "vibe3.services.shared.label_anomalies",
    "LabelService": "vibe3.services.shared.label_service",
    "classify_dispatch_eligibility": "vibe3.services.shared.labels",
    "clean_old_state_labels": "vibe3.services.shared.labels",
    "collect_label_anomalies": "vibe3.services.shared.label_anomalies",
    "get_conflicting_states": "vibe3.services.shared.labels",
    "get_highest_priority_state": "vibe3.services.shared.labels",
    "get_state_labels": "vibe3.services.shared.labels",
    "has_execution_state": "vibe3.services.shared.labels",
    "has_manager_assignee": "vibe3.services.shared.labels",
    "has_orchestra_governed": "vibe3.services.shared.labels",
    "has_roadmap_conflict": "vibe3.services.shared.labels",
    "has_roadmap_label": "vibe3.services.shared.labels",
    "normalize_assignees": "vibe3.services.shared.labels",
    "normalize_labels": "vibe3.services.shared.labels",
    "ORCHESTRA_GOVERNED_LABEL": "vibe3.services.shared.labels",
    "should_skip_from_queue": "vibe3.services.shared.labels",
    # loc
    "LOCStats": "vibe3.services.shared.loc",
    "LocService": "vibe3.services.shared.loc",
    # branches
    "resolve_branch_and_issue": "vibe3.services.shared.branches",
    "resolve_branch_arg": "vibe3.services.shared.branches",
    # roles
    "get_role_block_function": "vibe3.services.shared.roles",
    # signatures
    "AI_ASSISTANT_ACTORS": "vibe3.services.shared.signatures",
    "WORKFLOW_ACTOR": "vibe3.services.shared.signatures",
    "SignatureService": "vibe3.services.shared.signatures",
    # timeline
    "parse_timeline_from_comments": "vibe3.services.shared.timeline",
    # versions
    "VersionService": "vibe3.services.shared.versions",
}


def __getattr__(name: str) -> Any:
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        globals()[name] = symbol
        return symbol
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
