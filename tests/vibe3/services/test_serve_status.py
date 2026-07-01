"""Tests for serve status service severity-aware display."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from vibe3.clients import SQLiteClient
from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService


@pytest.fixture(autouse=True)
def reset_error_tracking() -> Iterator[None]:
    """Reset ErrorTrackingService singleton between tests to prevent state leakage."""
    yield
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


def test_status_shows_severity_breakdown(temp_store: SQLiteClient) -> None:
    """Test that serve status displays severity breakdown."""
    ErrorTrackingService._registry[temp_store.db_path] = ErrorTrackingService(
        store=temp_store
    )

    # Record errors with different severities
    ErrorTrackingService.get_instance(store=temp_store).record_error(
        error_code="E_MODEL_NOT_FOUND",
        error_message="Model not found",  # CRITICAL
    )
    ErrorTrackingService.get_instance(store=temp_store).record_error(
        error_code="E_API_RATE_LIMIT",
        error_message="Rate limit",  # ERROR
    )
    ErrorTrackingService.get_instance(store=temp_store).record_error(
        error_code="E_EXEC_NO_OUTPUT",
        error_message="No output",  # WARNING
    )
    ErrorTrackingService.get_instance(store=temp_store).record_error(
        error_code="E_CAPACITY_SKIP",
        error_message="Skip",  # WARNING
    )

    # Get status
    status = ErrorTrackingService.get_instance(store=temp_store).get_status()

    # Check severity-based counts
    assert status["critical_count"] == 1
    assert status["error_count"] == 1
    assert status["warning_count"] == 2
    assert status["total_errors"] == 4
