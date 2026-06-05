"""Vibe3 clients layer."""

# Core clients
# AI clients
from vibe3.clients.ai_client import AIClient
from vibe3.clients.ai_suggestion_client import AISuggestionClient
from vibe3.clients.git_client import GitClient, find_repo_root

# Worktree operations
from vibe3.clients.git_worktree_ops import prune_worktrees, remove_worktree
from vibe3.clients.github_client import GitHubClient

# Issue parsing utilities
from vibe3.clients.github_issues_ops import parse_blocked_by, parse_linked_issues

# Labels
from vibe3.clients.github_labels import GhIssueLabelPort, IssueLabelPort

# Caches
from vibe3.clients.merged_pr_cache import MergedPRCache

# Protocols
from vibe3.clients.protocols import BackendProtocol, GitHubClientProtocol
from vibe3.clients.recent_pr_cache import RecentPRCache

# Runtime assets
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
from vibe3.clients.store_context import get_store

__all__ = [
    # Protocols
    "BackendProtocol",
    "GitHubClientProtocol",
    # Core clients
    "GitClient",
    "GitHubClient",
    "SQLiteClient",
    "SerenaClient",
    # Labels
    "GhIssueLabelPort",
    "IssueLabelPort",
    # Runtime assets
    "runtime_assets_root",
    "resolve_runtime_asset",
    "check_runtime_asset",
    "resolve_prompt_config",
    # Issue parsing
    "parse_blocked_by",
    "parse_linked_issues",
    # Worktree operations
    "remove_worktree",
    "prune_worktrees",
    # Caches
    "MergedPRCache",
    "RecentPRCache",
    # AI clients
    "AIClient",
    "AISuggestionClient",
    # Utilities
    "count_references",
    "extract_function_names",
    "find_repo_root",
    "get_store",
]
