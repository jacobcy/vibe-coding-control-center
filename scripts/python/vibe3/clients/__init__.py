"""Vibe3 clients layer."""

from vibe3.clients.serena_client import (
    SerenaClient,
    SerenaClientError,
    count_references,
    extract_function_names,
)

__all__ = [
    "SerenaClient",
    "SerenaClientError",
    "count_references",
    "extract_function_names",
]
