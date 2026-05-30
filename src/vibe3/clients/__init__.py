"""Vibe3 clients layer."""

from vibe3.clients.ai_suggestion_client import AISuggestionClient
from vibe3.clients.git_client import GitClient, GitClientProtocol, find_repo_root
from vibe3.clients.git_worktree_ops import prune_worktrees, remove_worktree
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_blocked_by, parse_linked_issues
from vibe3.clients.github_labels import GhIssueLabelPort, IssueLabelPort
from vibe3.clients.merged_pr_cache import MergedPRCache
from vibe3.clients.protocols import BackendProtocol, GitHubClientProtocol
from vibe3.clients.recent_pr_cache import RecentPRCache
from vibe3.clients.serena_client import (
    SerenaClient,
    count_references,
    extract_function_names,
)
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.clients.store_context import get_store

__all__ = [
    "AISuggestionClient",
    "BackendProtocol",
    "GitClient",
    "GitClientProtocol",
    "GitHubClient",
    "GitHubClientProtocol",
    "GhIssueLabelPort",
    "IssueLabelPort",
    "MergedPRCache",
    "RecentPRCache",
    "SerenaClient",
    "SQLiteClient",
    "count_references",
    "extract_function_names",
    "find_repo_root",
    "get_store",
    "init_schema",
    "parse_blocked_by",
    "parse_linked_issues",
    "prune_worktrees",
    "remove_worktree",
]
