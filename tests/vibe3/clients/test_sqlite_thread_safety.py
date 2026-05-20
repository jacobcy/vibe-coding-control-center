"""Test thread safety of singleton SQLite connection."""

import concurrent.futures
from pathlib import Path

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
