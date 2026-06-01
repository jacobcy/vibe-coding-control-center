"""Vibe3 clients layer."""

from vibe3.clients.git_client import GitClient, find_repo_root
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.protocols import BackendProtocol
from vibe3.clients.serena_client import (
    SerenaClient,
    count_references,
    extract_function_names,
)
from vibe3.clients.sqlite_client import SQLiteClient

__all__ = [
    "BackendProtocol",
    "GitClient",
    "GitHubClient",
    "SerenaClient",
    "SQLiteClient",
    "count_references",
    "extract_function_names",
    "find_repo_root",
]
