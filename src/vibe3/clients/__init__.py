"""Vibe3 clients layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.clients.ai_client import AIClient
    from vibe3.clients.ai_suggestion_client import AISuggestionClient
    from vibe3.clients.git_client import GitClient, GitClientProtocol, find_repo_root
    from vibe3.clients.git_worktree_ops import prune_worktrees, remove_worktree
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.github_field_constants import (
        GITHUB_DEFAULT_VIEW_FIELDS,
        GITHUB_FIELDS_BODY_COMMENTS,
        GITHUB_FIELDS_BODY_ONLY,
        GITHUB_FIELDS_COMMENTS_ONLY,
        GITHUB_FIELDS_FULL_WITH_COMMENTS,
        GITHUB_FIELDS_STATE_ONLY,
        GITHUB_FIELDS_TITLE_ONLY,
    )
    from vibe3.clients.github_issues_ops import parse_blocked_by, parse_linked_issues
    from vibe3.clients.github_labels import GhIssueLabelPort, IssueLabelPort
    from vibe3.clients.label_utils import (
        LabelAnomaly,
        collect_label_anomalies,
        has_manager_assignee,
        normalize_assignees,
        normalize_labels,
    )
    from vibe3.clients.merged_pr_cache import MergedPRCache
    from vibe3.clients.protocols.backend import BackendProtocol
    from vibe3.clients.protocols.flow import FlowReader, FlowStatePort
    from vibe3.clients.protocols.git import GitPathProtocol
    from vibe3.clients.protocols.github import GitHubClientProtocol
    from vibe3.clients.protocols.pr import BaseResolver
    from vibe3.clients.protocols.role import TriggerableRoleDefinitionProtocol
    from vibe3.clients.recent_pr_cache import RecentPRCache
    from vibe3.clients.runtime_assets import (
        check_runtime_asset,
        resolve_prompt_config,
        resolve_runtime_asset,
        runtime_assets_root,
    )
    from vibe3.clients.serena_client import (
        SerenaClient,
        count_references,
        extract_function_names,
    )
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.clients.sqlite_schema import init_schema
    from vibe3.clients.store_context import get_store
    from vibe3.clients.sync_rules import (
        LocalSyncRules,
        RemoteSyncRules,
        SyncRule,
        SyncRulesConfig,
        load_sync_rules,
    )

# Lazy imports (for complex dependencies and GitHub field constants)
_LAZY_IMPORTS = {
    "AIClient": "vibe3.clients.ai_client",
    "AISuggestionClient": "vibe3.clients.ai_suggestion_client",
    "BackendProtocol": "vibe3.clients.protocols.backend",
    "BaseResolver": "vibe3.clients.protocols.pr",
    "FlowReader": "vibe3.clients.protocols.flow",
    "FlowStatePort": "vibe3.clients.protocols.flow",
    "GITHUB_DEFAULT_VIEW_FIELDS": "vibe3.clients.github_field_constants",
    "GITHUB_FIELDS_BODY_COMMENTS": "vibe3.clients.github_field_constants",
    "GITHUB_FIELDS_BODY_ONLY": "vibe3.clients.github_field_constants",
    "GITHUB_FIELDS_COMMENTS_ONLY": "vibe3.clients.github_field_constants",
    "GITHUB_FIELDS_FULL_WITH_COMMENTS": "vibe3.clients.github_field_constants",
    "GITHUB_FIELDS_STATE_ONLY": "vibe3.clients.github_field_constants",
    "GITHUB_FIELDS_TITLE_ONLY": "vibe3.clients.github_field_constants",
    "GhIssueLabelPort": "vibe3.clients.github_labels",
    "GitClient": "vibe3.clients.git_client",
    "GitClientProtocol": "vibe3.clients.git_client",
    "GitHubClient": "vibe3.clients.github_client",
    "GitHubClientProtocol": "vibe3.clients.protocols.github",
    "GitPathProtocol": "vibe3.clients.protocols.git",
    "IssueLabelPort": "vibe3.clients.github_labels",
    "LabelAnomaly": "vibe3.clients.label_utils",
    "LocalSyncRules": "vibe3.clients.sync_rules",
    "MergedPRCache": "vibe3.clients.merged_pr_cache",
    "RecentPRCache": "vibe3.clients.recent_pr_cache",
    "RemoteSyncRules": "vibe3.clients.sync_rules",
    "SerenaClient": "vibe3.clients.serena_client",
    "SQLiteClient": "vibe3.clients.sqlite_client",
    "SyncRule": "vibe3.clients.sync_rules",
    "SyncRulesConfig": "vibe3.clients.sync_rules",
    "TriggerableRoleDefinitionProtocol": "vibe3.clients.protocols.role",
    "check_runtime_asset": "vibe3.clients.runtime_assets",
    "collect_label_anomalies": "vibe3.clients.label_utils",
    "count_references": "vibe3.clients.serena_client",
    "extract_function_names": "vibe3.clients.serena_client",
    "find_repo_root": "vibe3.clients.git_client",
    "get_store": "vibe3.clients.store_context",
    "has_manager_assignee": "vibe3.clients.label_utils",
    "init_schema": "vibe3.clients.sqlite_schema",
    "load_sync_rules": "vibe3.clients.sync_rules",
    "normalize_assignees": "vibe3.clients.label_utils",
    "normalize_labels": "vibe3.clients.label_utils",
    "parse_blocked_by": "vibe3.clients.github_issues_ops",
    "parse_linked_issues": "vibe3.clients.github_issues_ops",
    "prune_worktrees": "vibe3.clients.git_worktree_ops",
    "remove_worktree": "vibe3.clients.git_worktree_ops",
    "resolve_prompt_config": "vibe3.clients.runtime_assets",
    "resolve_runtime_asset": "vibe3.clients.runtime_assets",
    "runtime_assets_root": "vibe3.clients.runtime_assets",
}


def __getattr__(name: str) -> object:
    """Lazy import for clients symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.clients import GitClient

    While avoiding circular imports at module load time.
    """
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AIClient",
    "AISuggestionClient",
    "BackendProtocol",
    "BaseResolver",
    "FlowReader",
    "FlowStatePort",
    "GITHUB_DEFAULT_VIEW_FIELDS",
    "GITHUB_FIELDS_BODY_COMMENTS",
    "GITHUB_FIELDS_BODY_ONLY",
    "GITHUB_FIELDS_COMMENTS_ONLY",
    "GITHUB_FIELDS_FULL_WITH_COMMENTS",
    "GITHUB_FIELDS_STATE_ONLY",
    "GITHUB_FIELDS_TITLE_ONLY",
    "GhIssueLabelPort",
    "GitClient",
    "GitClientProtocol",
    "GitHubClient",
    "GitHubClientProtocol",
    "GitPathProtocol",
    "IssueLabelPort",
    "LabelAnomaly",
    "LocalSyncRules",
    "MergedPRCache",
    "RecentPRCache",
    "RemoteSyncRules",
    "SerenaClient",
    "SQLiteClient",
    "SyncRule",
    "SyncRulesConfig",
    "TriggerableRoleDefinitionProtocol",
    "check_runtime_asset",
    "collect_label_anomalies",
    "count_references",
    "extract_function_names",
    "find_repo_root",
    "get_store",
    "has_manager_assignee",
    "init_schema",
    "load_sync_rules",
    "normalize_assignees",
    "normalize_labels",
    "parse_blocked_by",
    "parse_linked_issues",
    "prune_worktrees",
    "remove_worktree",
    "resolve_prompt_config",
    "resolve_runtime_asset",
    "runtime_assets_root",
]
