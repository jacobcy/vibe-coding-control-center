"""Tests for SQLiteClient context manager."""

from vibe3.clients import SQLiteClient, get_store


def test_get_store_provides_client():
    """get_store should yield SQLiteClient instance."""

    with get_store() as store:
        assert isinstance(store, SQLiteClient)


def test_get_store_context_isolation():
    """get_store should create new instance each time."""
    instances = []

    with get_store() as store1:
        instances.append(id(store1))

    with get_store() as store2:
        instances.append(id(store2))

    # Each call should create new instance
    assert instances[0] != instances[1]
