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

    ErrorTrackingService._instance = None


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
