"""Tests for FailedGate module (SQLite-based implementation)."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from vibe3.clients import SQLiteClient
from vibe3.orchestra.failed_gate import FailedGate


@pytest.fixture(autouse=True)
def reset_error_tracking() -> Iterator[None]:
    """Reset ErrorTrackingService singleton between tests to prevent state leakage."""
    yield
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    ErrorTrackingService.clear_instance()


@pytest.fixture
def temp_store(tmp_path: Path) -> SQLiteClient:
    """Create a temporary SQLiteClient for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from vibe3.clients.sqlite_schema import init_schema

    init_schema(conn)
    conn.close()
    return SQLiteClient(db_path=str(db_path))


def test_failed_gate_open(temp_store: SQLiteClient) -> None:
    """Gate should be open when no errors are recorded."""
    gate = FailedGate(store=temp_store)
    result = gate.check()

    assert not result.blocked
    assert result.reason is None


def test_failed_gate_blocked_by_model_error(temp_store: SQLiteClient) -> None:
    """Gate should block immediately on model config errors."""
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    # Create ErrorTrackingService with test database
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Record a model error
    ErrorTrackingService._instance.record_error("E_MODEL_NOT_FOUND", "Model not found")

    gate = FailedGate(store=temp_store)
    result = gate.check()

    assert result.blocked
    assert "Model configuration errors" in (result.reason or "")


def test_failed_gate_blocked_by_api_threshold(temp_store: SQLiteClient) -> None:
    """Gate should block when API error threshold is reached."""
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    # Create ErrorTrackingService with test database
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Record 2 API errors (threshold is 2 in 3 ticks)
    ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT", "Rate limit", tick_id=1
    )
    ErrorTrackingService._instance.record_error("E_API_TIMEOUT", "Timeout", tick_id=2)

    gate = FailedGate(store=temp_store)
    result = gate.check()

    assert result.blocked
    assert "API error threshold" in (result.reason or "")


def test_failed_gate_clear(temp_store: SQLiteClient) -> None:
    """Gate should clear and allow operation after manual resume."""
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    # Create ErrorTrackingService with test database
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Record an error and trigger gate
    ErrorTrackingService._instance.record_error("E_MODEL_NOT_FOUND", "Model error")

    gate = FailedGate(store=temp_store)
    result = gate.check()
    assert result.blocked

    # Clear the gate
    gate.clear(cleared_by="admin:manual", reason="Fixed model config")

    # Check again - should be open
    result = gate.check()
    assert not result.blocked


def test_failed_gate_persists_state(temp_store: SQLiteClient) -> None:
    """Gate state should persist across instances."""
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    # Create ErrorTrackingService with test database
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Record error with first instance
    ErrorTrackingService._instance.record_error(
        "E_MODEL_PERMISSION", "Permission denied"
    )

    gate1 = FailedGate(store=temp_store)
    result1 = gate1.check()
    assert result1.blocked

    # Create new instance - should load state from DB
    gate2 = FailedGate(store=temp_store)
    result2 = gate2.check()
    assert result2.blocked
    assert result2.reason == result1.reason


def test_failed_gate_increment_blocked_ticks(temp_store: SQLiteClient) -> None:
    """Gate should increment blocked_ticks when active."""
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    # Create ErrorTrackingService with test database
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Trigger gate
    ErrorTrackingService._instance.record_error("E_MODEL_CONFIG", "Config error")

    gate = FailedGate(store=temp_store)
    result = gate.check()
    assert result.blocked
    assert result.blocked_ticks == 0

    # Increment ticks
    gate.increment_blocked_ticks()
    gate.increment_blocked_ticks()

    # Check status
    status = gate.get_status()
    assert status.blocked_ticks == 2


def test_per_db_path_instance_isolation(tmp_path: Path) -> None:
    """Different db_path instances should be isolated."""
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    # Create two separate databases
    db_path1 = tmp_path / "test1.db"
    db_path2 = tmp_path / "test2.db"

    for db_path in [db_path1, db_path2]:
        conn = sqlite3.connect(db_path)
        from vibe3.clients.sqlite_schema import init_schema

        init_schema(conn)
        conn.close()

    store1 = SQLiteClient(db_path=str(db_path1))
    store2 = SQLiteClient(db_path=str(db_path2))

    # Get instances keyed by db_path
    instance1 = ErrorTrackingService.get_instance(store=store1)
    instance2 = ErrorTrackingService.get_instance(store=store2)

    # Should be different instances
    assert instance1 is not instance2
    assert instance1.db_path != instance2.db_path

    # Record error in instance1
    instance1.record_error("E_MODEL_TEST", "Test error in db1")

    # instance2 should not see the error (different database)
    assert instance1.has_model_config_error()
    assert not instance2.has_model_config_error()

    # Clear instance1's registry entry (not the error data)
    ErrorTrackingService.clear_instance(db_path=str(db_path1))

    # Get a new instance for store1
    instance1_new = ErrorTrackingService.get_instance(store=store1)

    # New instance still sees the error data (same database)
    # This is expected - clear_instance() only clears the in-memory instance, not the DB
    assert instance1_new.has_model_config_error()

    # instance2 still unaffected
    assert not instance2.has_model_config_error()


def test_clear_instance_specific_db_path(tmp_path: Path) -> None:
    """clear_instance(db_path) should only clear that instance."""
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    # Create two separate databases
    db_path1 = tmp_path / "test1.db"
    db_path2 = tmp_path / "test2.db"

    for db_path in [db_path1, db_path2]:
        conn = sqlite3.connect(db_path)
        from vibe3.clients.sqlite_schema import init_schema

        init_schema(conn)
        conn.close()

    store1 = SQLiteClient(db_path=str(db_path1))
    store2 = SQLiteClient(db_path=str(db_path2))

    # Create instances
    instance1 = ErrorTrackingService.get_instance(store=store1)
    instance2 = ErrorTrackingService.get_instance(store=store2)

    # Record errors in both
    instance1.record_error("E_API_TEST1", "Error 1")
    instance2.record_error("E_API_TEST2", "Error 2")

    # Clear instance1's registry entry (not the error data)
    ErrorTrackingService.clear_instance(db_path=str(db_path1))

    # Get new instances
    instance1_new = ErrorTrackingService.get_instance(store=store1)
    instance2_new = ErrorTrackingService.get_instance(store=store2)

    # Both still see their error data (same databases)
    # clear_instance() only clears in-memory instance, not DB
    assert instance1_new.get_api_error_count() == 1
    assert instance2_new.get_api_error_count() == 1

    # But instance2 is still the same object (not cleared)
    assert instance2_new is instance2


def test_get_instance_with_and_without_store(tmp_path: Path) -> None:
    """get_instance() without store should return default instance."""
    from vibe3.exceptions.error_tracking import ErrorTrackingService

    # Clear any existing state
    ErrorTrackingService.clear_instance()

    # Get default instance
    default_instance = ErrorTrackingService.get_instance()
    assert default_instance is not None

    # Get default instance again - should be same object
    default_instance2 = ErrorTrackingService.get_instance()
    assert default_instance is default_instance2

    # Create a separate db_path instance
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from vibe3.clients.sqlite_schema import init_schema

    init_schema(conn)
    conn.close()

    store = SQLiteClient(db_path=str(db_path))
    custom_instance = ErrorTrackingService.get_instance(store=store)

    # Should be different from default instance
    assert custom_instance is not default_instance
    assert custom_instance.db_path != default_instance.db_path

    # Clear default instance
    ErrorTrackingService.clear_instance()
    default_instance3 = ErrorTrackingService.get_instance()
    assert default_instance3 is not default_instance

    # Custom instance should still be accessible
    custom_instance2 = ErrorTrackingService.get_instance(store=store)
    assert custom_instance2 is custom_instance
