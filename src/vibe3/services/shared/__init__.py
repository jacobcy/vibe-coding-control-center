"""Shared utilities and services for vibe3."""

from typing import Any

__all__ = [
    # Error helpers
    "has_recent_specific_error",
    "record_error",
    "record_dispatch_failure_if_unexpected",
    # Actor utilities
    "resolve_actor_backend_model",
    "format_agent_actor",
    "extract_role_from_actor",
    # Label utilities and services
    "normalize_labels",
    "normalize_assignees",
    "has_manager_assignee",
    "should_skip_from_queue",
    "clean_old_state_labels",
    "LabelService",
    # Orchestra helpers
    "get_manager_usernames",
    "get_handoff_state_label",
    # Verdict utilities
    "ALL_VERDICTS",
    "PASSING_VERDICTS",
    "AUDIT_REQUIRED_VERDICTS",
    "MERGE_BLOCKING_VERDICTS",
    "passes_review",
    "requires_audit_ref",
    "blocks_merge",
    # Artifact parsing
    "ArtifactParser",
    # Timeline utilities
    "parse_timeline_from_comments",
]

_SYMBOL_MODULES = {
    # Error helpers
    "has_recent_specific_error": "vibe3.services.shared.errors",
    "record_error": "vibe3.services.shared.errors",
    "record_dispatch_failure_if_unexpected": "vibe3.services.shared.errors",
    # Actor utilities
    "resolve_actor_backend_model": "vibe3.services.shared.actors",
    "format_agent_actor": "vibe3.services.shared.actors",
    "extract_role_from_actor": "vibe3.services.shared.actors",
    # Label utilities and services
    "normalize_labels": "vibe3.services.shared.labels",
    "normalize_assignees": "vibe3.services.shared.labels",
    "has_manager_assignee": "vibe3.services.shared.labels",
    "should_skip_from_queue": "vibe3.services.shared.labels",
    "clean_old_state_labels": "vibe3.services.shared.labels",
    "LabelService": "vibe3.services.shared.labels",
    # Orchestra helpers
    "get_manager_usernames": "vibe3.services.shared.orchestra",
    "get_handoff_state_label": "vibe3.services.shared.orchestra",
    # Verdict utilities
    "ALL_VERDICTS": "vibe3.services.shared.verdicts",
    "PASSING_VERDICTS": "vibe3.services.shared.verdicts",
    "AUDIT_REQUIRED_VERDICTS": "vibe3.services.shared.verdicts",
    "MERGE_BLOCKING_VERDICTS": "vibe3.services.shared.verdicts",
    "passes_review": "vibe3.services.shared.verdicts",
    "requires_audit_ref": "vibe3.services.shared.verdicts",
    "blocks_merge": "vibe3.services.shared.verdicts",
    "ArtifactParser": "vibe3.services.shared.artifacts",
    # Timeline utilities
    "parse_timeline_from_comments": "vibe3.services.shared.timeline",
}


def __getattr__(name: str) -> Any:
    """Lazy import for shared utilities to avoid circular dependencies."""
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
