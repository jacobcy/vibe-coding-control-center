"""SQLiteClient context manager for dependency injection."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from vibe3.clients.sqlite_client import SQLiteClient


@contextmanager
def get_store() -> Iterator[SQLiteClient]:
    """Provide SQLiteClient instance with automatic cleanup.

    Yields:
        SQLiteClient instance

    Example:
        with get_store() as store:
            flow = store.read_flow(branch)
    """
    client = SQLiteClient()
    try:
        yield client
    finally:
        # SQLiteClient has no explicit close method, but we keep finally
        # for future extension
        pass
