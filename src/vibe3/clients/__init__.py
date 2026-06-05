"""Vibe3 clients layer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.clients.git_client import GitClient, find_repo_root
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.protocols import BackendProtocol
    from vibe3.clients.serena_client import (
        SerenaClient,
        count_references,
        extract_function_names,
    )
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.clients.store_context import get_store

# Lazy imports
_LAZY_IMPORTS = {
    "GitClient": "vibe3.clients.git_client",
    "find_repo_root": "vibe3.clients.git_client",
    "GitHubClient": "vibe3.clients.github_client",
    "BackendProtocol": "vibe3.clients.protocols",
    "SerenaClient": "vibe3.clients.serena_client",
    "count_references": "vibe3.clients.serena_client",
    "extract_function_names": "vibe3.clients.serena_client",
    "SQLiteClient": "vibe3.clients.sqlite_client",
    "get_store": "vibe3.clients.store_context",
}


def __getattr__(name: str) -> object:
    """Lazy import for clients symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BackendProtocol",
    "GitClient",
    "GitHubClient",
    "SerenaClient",
    "SQLiteClient",
    "count_references",
    "extract_function_names",
    "find_repo_root",
    "get_store",
]
