"""Test that singleton connection prevents FD exhaustion."""

import os
from pathlib import Path

import pytest

from vibe3.clients.sqlite_client import SQLiteClient

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not installed")
def test_fd_not_exhausted_under_high_frequency(tmp_path: Path) -> None:
    """Verify FD count does not grow under high-frequency operations."""
    db_path = str(tmp_path / "test.db")
    client = SQLiteClient(db_path=db_path)

    proc = psutil.Process(os.getpid())
    before = proc.num_fds()

    # Perform 1000 operations
    for i in range(1000):
        client.update_flow_state(
            f"test-branch-{i % 10}",
            flow_slug="test",
            flow_status="active",
        )
        state = client.get_flow_state(f"test-branch-{i % 10}")
        assert state is not None

    after = proc.num_fds()
    fd_growth = after - before

    # Singleton connection: FD should not grow significantly
    # Allow small growth for other resources, but not 1000+ FDs
    assert fd_growth < 5, f"FD grew by {fd_growth} (before={before}, after={after})"


@pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not installed")
def test_fd_not_exhausted_queue_operations(tmp_path: Path) -> None:
    """Verify queue operations do not exhaust FDs."""
    db_path = str(tmp_path / "test.db")
    client = SQLiteClient(db_path=db_path)

    proc = psutil.Process(os.getpid())
    before = proc.num_fds()

    # Perform 1000 queue operations using singleton connection (heartbeat pattern)
    for i in range(1000):
        client.replace_all_queue_entries(
            [
                {
                    "issue_number": i % 100,
                    "collected_state": f"state-{i}",
                    "retry_count": 0,
                }
            ]
        )
        entries = client.load_all_queue_entries()
        assert len(entries) > 0

    after = proc.num_fds()
    fd_growth = after - before

    assert fd_growth < 5, f"FD grew by {fd_growth}"


@pytest.mark.skipif(not HAS_PSUTIL, reason="psutil not installed")
def test_fd_not_exhausted_event_operations(tmp_path: Path) -> None:
    """Verify event operations do not exhaust FDs."""
    db_path = str(tmp_path / "test.db")
    client = SQLiteClient(db_path=db_path)

    proc = psutil.Process(os.getpid())
    before = proc.num_fds()

    # Perform 1000 event operations (dispatch pattern)
    for i in range(1000):
        client.add_event("test-branch", f"event_{i}", "test_actor")

    after = proc.num_fds()
    fd_growth = after - before

    assert fd_growth < 5, f"FD grew by {fd_growth}"
