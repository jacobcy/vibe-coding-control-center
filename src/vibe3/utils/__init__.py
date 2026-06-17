"""Utility modules for Vibe3."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.utils.actor_utils import normalize_actor
    from vibe3.utils.branch_compare import (
        check_branch_behind,
        format_branch_behind_body,
        format_branch_behind_console,
    )
    from vibe3.utils.branch_utils import find_parent_branch, is_branch_merged_to_main
    from vibe3.utils.codeagent_helpers import (
        diagnose_backend_error,
        diagnose_prompt_size_issue,
        sanitize_prompt_for_display,
        sanitize_task_shell_meta,
        stream_reader,
        summarize_backend_output,
    )
    from vibe3.utils.constants import (
        AUTOMATED_MARKERS,
        CODEAGENT_STDIN_MODE_THRESHOLD,
        DEFAULT_MODULE_GROWTH_THRESHOLD,
        EVENT_REQUIRED_REF_MISSING,
        EVENT_STATE_TRANSITIONED,
        EVENT_STATE_UNCHANGED,
        EVENT_TRANSITION_COUNT_EXCEEDED,
        GENERIC_AGENT_MARKER_PATTERN,
        PACK_REFS_INTERVAL_TICKS,
        STARTING_TIMEOUT_SECONDS,
        VERDICT_UNKNOWN,
    )
    from vibe3.utils.error_message_cleaner import (
        CODEAGENT_WRAPPER_ANYWHERE_RE,
        CODEAGENT_WRAPPER_RE,
        clean_error_message,
    )
    from vibe3.utils.git_helpers import (
        find_repo_root,
        get_branch_handoff_dir,
        get_commit_message,
        get_current_branch,
        get_git_common_dir,
        get_remote_url,
    )
    from vibe3.utils.hash_helpers import (
        compute_governance_hash,
        compute_hash_from_loader,
    )
    from vibe3.utils.issue_ref import parse_issue_number, try_parse_issue_number
    from vibe3.utils.orchestra_instance import (
        OrchestraInstanceInfo,
        read_instance_info,
        validate_instance,
        write_instance_info,
    )
    from vibe3.utils.paths import (
        get_vibe3_cache_path,
        get_vibe3_db_path,
        get_vibe3_log_dir,
    )
    from vibe3.utils.queue_ordering import (
        resolve_milestone_rank,
        resolve_priority,
        resolve_roadmap_rank,
        sort_ready_issues,
    )
    from vibe3.utils.serve_helpers import (
        ORCHESTRA_TMUX_SESSION,
        job_to_dict,
        orchestra_tmux_session_exists,
        validate_pid_file,
    )
    from vibe3.utils.time_format import format_age_aware_time

# Lazy imports
_LAZY_IMPORTS = {
    "AUTOMATED_MARKERS": "vibe3.utils.constants",
    "CODEAGENT_STDIN_MODE_THRESHOLD": "vibe3.utils.constants",
    "CODEAGENT_WRAPPER_ANYWHERE_RE": "vibe3.utils.error_message_cleaner",
    "CODEAGENT_WRAPPER_RE": "vibe3.utils.error_message_cleaner",
    "DEFAULT_MODULE_GROWTH_THRESHOLD": "vibe3.utils.constants",
    "EVENT_REQUIRED_REF_MISSING": "vibe3.utils.constants",
    "EVENT_STATE_TRANSITIONED": "vibe3.utils.constants",
    "EVENT_STATE_UNCHANGED": "vibe3.utils.constants",
    "EVENT_TRANSITION_COUNT_EXCEEDED": "vibe3.utils.constants",
    "GENERIC_AGENT_MARKER_PATTERN": "vibe3.utils.constants",
    "PACK_REFS_INTERVAL_TICKS": "vibe3.utils.constants",
    "STARTING_TIMEOUT_SECONDS": "vibe3.utils.constants",
    "clean_error_message": "vibe3.utils.error_message_cleaner",
    "diagnose_backend_error": "vibe3.utils.codeagent_helpers",
    "diagnose_prompt_size_issue": "vibe3.utils.codeagent_helpers",
    "find_parent_branch": "vibe3.utils.branch_utils",
    "is_branch_merged_to_main": "vibe3.utils.branch_utils",
    "format_age_aware_time": "vibe3.utils.time_format",
    "format_branch_behind_body": "vibe3.utils.branch_compare",
    "format_branch_behind_console": "vibe3.utils.branch_compare",
    "get_branch_handoff_dir": "vibe3.utils.git_helpers",
    "get_commit_message": "vibe3.utils.git_helpers",
    "get_current_branch": "vibe3.utils.git_helpers",
    "get_git_common_dir": "vibe3.utils.git_helpers",
    "get_remote_url": "vibe3.utils.git_helpers",
    "compute_governance_hash": "vibe3.utils.hash_helpers",
    "compute_hash_from_loader": "vibe3.utils.hash_helpers",
    "get_vibe3_cache_path": "vibe3.utils.paths",
    "get_vibe3_db_path": "vibe3.utils.paths",
    "get_vibe3_log_dir": "vibe3.utils.paths",
    "find_repo_root": "vibe3.utils.git_helpers",
    "normalize_actor": "vibe3.utils.actor_utils",
    "OrchestraInstanceInfo": "vibe3.utils.orchestra_instance",
    "parse_issue_number": "vibe3.utils.issue_ref",
    "read_instance_info": "vibe3.utils.orchestra_instance",
    "resolve_milestone_rank": "vibe3.utils.queue_ordering",
    "resolve_priority": "vibe3.utils.queue_ordering",
    "resolve_roadmap_rank": "vibe3.utils.queue_ordering",
    "sanitize_prompt_for_display": "vibe3.utils.codeagent_helpers",
    "sanitize_task_shell_meta": "vibe3.utils.codeagent_helpers",
    "sort_ready_issues": "vibe3.utils.queue_ordering",
    "stream_reader": "vibe3.utils.codeagent_helpers",
    "summarize_backend_output": "vibe3.utils.codeagent_helpers",
    "try_parse_issue_number": "vibe3.utils.issue_ref",
    "validate_instance": "vibe3.utils.orchestra_instance",
    "VERDICT_UNKNOWN": "vibe3.utils.constants",
    "write_instance_info": "vibe3.utils.orchestra_instance",
    "check_branch_behind": "vibe3.utils.branch_compare",
    "ORCHESTRA_TMUX_SESSION": "vibe3.utils.serve_helpers",
    "job_to_dict": "vibe3.utils.serve_helpers",
    "orchestra_tmux_session_exists": "vibe3.utils.serve_helpers",
    "validate_pid_file": "vibe3.utils.serve_helpers",
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
    "CODEAGENT_STDIN_MODE_THRESHOLD",
    "CODEAGENT_WRAPPER_ANYWHERE_RE",
    "CODEAGENT_WRAPPER_RE",
    "DEFAULT_MODULE_GROWTH_THRESHOLD",
    "EVENT_REQUIRED_REF_MISSING",
    "EVENT_STATE_TRANSITIONED",
    "EVENT_STATE_UNCHANGED",
    "EVENT_TRANSITION_COUNT_EXCEEDED",
    "GENERIC_AGENT_MARKER_PATTERN",
    "PACK_REFS_INTERVAL_TICKS",
    "STARTING_TIMEOUT_SECONDS",
    "VERDICT_UNKNOWN",
    "clean_error_message",
    "check_branch_behind",
    "compute_governance_hash",
    "compute_hash_from_loader",
    "diagnose_backend_error",
    "diagnose_prompt_size_issue",
    "find_parent_branch",
    "is_branch_merged_to_main",
    "format_age_aware_time",
    "format_branch_behind_body",
    "format_branch_behind_console",
    "get_branch_handoff_dir",
    "get_commit_message",
    "get_current_branch",
    "get_git_common_dir",
    "get_remote_url",
    "get_vibe3_cache_path",
    "get_vibe3_db_path",
    "get_vibe3_log_dir",
    "find_repo_root",
    "normalize_actor",
    "OrchestraInstanceInfo",
    "parse_issue_number",
    "read_instance_info",
    "resolve_milestone_rank",
    "resolve_priority",
    "resolve_roadmap_rank",
    "sanitize_prompt_for_display",
    "sanitize_task_shell_meta",
    "stream_reader",
    "sort_ready_issues",
    "summarize_backend_output",
    "try_parse_issue_number",
    "validate_instance",
    "write_instance_info",
    "ORCHESTRA_TMUX_SESSION",
    "job_to_dict",
    "orchestra_tmux_session_exists",
    "validate_pid_file",
]
