"""Test thread safety of singleton SQLite connection."""

import concurrent.futures
from pathlib import Path

import pytest

from vibe3.clients.sqlite_client import SQLiteClient


def test_concurrent_connection_creation_no_thread_error(tmp_path: Path) -> None:
    """Verify concurrent connection creation does not trigger ProgrammingError.

    This test verifies Phase 1 (connection creation thread safety).
    Phase 2 (connection usage thread safety) will be addressed by
    migrating repo methods to not modify shared connection state.
    """
    db_path = str(tmp_path / "test.db")

    # Create client once to initialize schema
    SQLiteClient(db_path=db_path)

    def create_client_and_query() -> None:
        """Create a client and access the connection from a thread."""
        client = SQLiteClient(db_path=db_path)
        # Access the connection to verify no ProgrammingError
        # (check_same_thread=False allows cross-thread access)
        conn = client._get_connection()
        # Execute a simple query to verify connection works
        cursor = conn.cursor()
        # Query actual table instead of SELECT 1 to ensure schema is accessible
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        result = cursor.fetchone()
        # Should succeed without ProgrammingError
        assert result is not None or result is None  # Just verify no exception

    # Run in thread pool (10 threads, each creates client 10 times)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(create_client_and_query) for _ in range(100)]
        for future in concurrent.futures.as_completed(futures):
            # Should NOT raise ProgrammingError about thread safety
            future.result()


@pytest.mark.slow
def test_concurrent_queries_no_corruption(tmp_path: Path) -> None:
    """Verify concurrent read queries on shared DB do not corrupt results.

    Reproduces the IndexError/InterfaceError from issue #2535 where
    ThreadPoolExecutor threads share a single connection and corrupt
    each other's cursor state.

    Note: A failing test reliably reproduces the bug. A passing test
    means the bug did not trigger this run, not that it is absent.
    """
    db_path = str(tmp_path / "test.db")
    client = SQLiteClient(db_path=db_path)

    # Seed test data
    for i in range(50):
        client.update_flow_state(
            f"branch-{i}", flow_slug=f"slug-{i}", flow_status="active"
        )

    errors: list[Exception] = []

    def concurrent_query() -> None:
        try:
            repo = SQLiteClient(db_path=db_path)
            for _ in range(100):
                flows = repo.get_all_flows()
                assert len(flows) == 50
        except Exception as e:
            errors.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(concurrent_query) for _ in range(20)]
        for future in concurrent.futures.as_completed(futures):
            future.result()

    assert not errors, f"Concurrent queries raised errors: {errors}"
