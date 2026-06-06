"""Utility modules for Vibe3."""

from __future__ import annotations

from typing import TYPE_CHECKING

# Cross-module imports (not self-references)
from vibe3.clients.runtime_assets import (
    resolve_prompt_config,
    resolve_runtime_asset,
    runtime_assets_root,
)

if TYPE_CHECKING:
    from vibe3.utils.actor_utils import normalize_actor
    from vibe3.utils.branch_utils import find_parent_branch
    from vibe3.utils.codeagent_helpers import (
        build_prompt_file_content,
        diagnose_backend_error,
        diagnose_prompt_size_issue,
        prepare_prompt_file,
        sanitize_prompt_for_display,
        sanitize_task_shell_meta,
        stream_reader,
        summarize_backend_output,
    )
    from vibe3.utils.comment_utils import is_human_comment
    from vibe3.utils.constants import (
        AUTOMATED_MARKERS,
        EVENT_REQUIRED_REF_MISSING,
        EVENT_STATE_TRANSITIONED,
        EVENT_STATE_UNCHANGED,
        EVENT_TRANSITION_COUNT_EXCEEDED,
        GENERIC_AGENT_MARKER_PATTERN,
        STARTING_TIMEOUT_SECONDS,
        VERDICT_UNKNOWN,
    )
    from vibe3.utils.error_message_cleaner import (
        CODEAGENT_WRAPPER_RE,
        clean_error_message,
    )
    from vibe3.utils.git_helpers import get_branch_handoff_dir, get_commit_message
    from vibe3.utils.issue_ref import try_parse_issue_number
    from vibe3.utils.time_format import format_age_aware_time

# Lazy imports
_LAZY_IMPORTS = {
    "AUTOMATED_MARKERS": "vibe3.utils.constants",
    "CODEAGENT_WRAPPER_RE": "vibe3.utils.error_message_cleaner",
    "EVENT_REQUIRED_REF_MISSING": "vibe3.utils.constants",
    "EVENT_STATE_TRANSITIONED": "vibe3.utils.constants",
    "EVENT_STATE_UNCHANGED": "vibe3.utils.constants",
    "EVENT_TRANSITION_COUNT_EXCEEDED": "vibe3.utils.constants",
    "GENERIC_AGENT_MARKER_PATTERN": "vibe3.utils.constants",
    "STARTING_TIMEOUT_SECONDS": "vibe3.utils.constants",
    "build_prompt_file_content": "vibe3.utils.codeagent_helpers",
    "clean_error_message": "vibe3.utils.error_message_cleaner",
    "diagnose_backend_error": "vibe3.utils.codeagent_helpers",
    "diagnose_prompt_size_issue": "vibe3.utils.codeagent_helpers",
    "find_parent_branch": "vibe3.utils.branch_utils",
    "format_age_aware_time": "vibe3.utils.time_format",
    "get_branch_handoff_dir": "vibe3.utils.git_helpers",
    "get_commit_message": "vibe3.utils.git_helpers",
    "is_human_comment": "vibe3.utils.comment_utils",
    "normalize_actor": "vibe3.utils.actor_utils",
    "prepare_prompt_file": "vibe3.utils.codeagent_helpers",
    "sanitize_prompt_for_display": "vibe3.utils.codeagent_helpers",
    "sanitize_task_shell_meta": "vibe3.utils.codeagent_helpers",
    "stream_reader": "vibe3.utils.codeagent_helpers",
    "summarize_backend_output": "vibe3.utils.codeagent_helpers",
    "try_parse_issue_number": "vibe3.utils.issue_ref",
    "VERDICT_UNKNOWN": "vibe3.utils.constants",
}


def __getattr__(name: str) -> object:
    """Lazy import for utils symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AUTOMATED_MARKERS",
    "CODEAGENT_WRAPPER_RE",
    "EVENT_REQUIRED_REF_MISSING",
    "EVENT_STATE_TRANSITIONED",
    "EVENT_STATE_UNCHANGED",
    "EVENT_TRANSITION_COUNT_EXCEEDED",
    "GENERIC_AGENT_MARKER_PATTERN",
    "STARTING_TIMEOUT_SECONDS",
    "VERDICT_UNKNOWN",
    "build_prompt_file_content",
    "clean_error_message",
    "diagnose_backend_error",
    "diagnose_prompt_size_issue",
    "find_parent_branch",
    "format_age_aware_time",
    "get_branch_handoff_dir",
    "get_commit_message",
    "is_human_comment",
    "normalize_actor",
    "prepare_prompt_file",
    "resolve_prompt_config",
    "resolve_runtime_asset",
    "runtime_assets_root",
    "sanitize_prompt_for_display",
    "sanitize_task_shell_meta",
    "stream_reader",
    "summarize_backend_output",
    "try_parse_issue_number",
]
