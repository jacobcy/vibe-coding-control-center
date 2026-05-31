"""Vibe3 clients layer."""

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.serena_client import (
    SerenaClient,
    count_references,
    extract_function_names,
)
from vibe3.clients.sqlite_client import SQLiteClient

__all__ = [
    "GitClient",
    "GitHubClient",
    "SerenaClient",
    "SQLiteClient",
    "count_references",
    "extract_function_names",
]
