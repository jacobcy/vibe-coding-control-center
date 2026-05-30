"""Integration tests for error severity refactor."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from vibe3.clients import SQLiteClient
from vibe3.orchestra.failed_gate import FailedGate
from vibe3.services import ErrorTrackingService


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


def test_scenario_warning_no_gate_close(temp_store: SQLiteClient) -> None:
    """Test that multiple warnings don't close gate."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    gate = FailedGate(store=temp_store)

    # Record 5 warnings
    for i in range(5):
        ErrorTrackingService.get_instance().record_error(
            error_code="E_EXEC_NO_OUTPUT",
            error_message=f"Warning {i}",
        )

    # Gate should remain open
    result = gate.check()
    assert not result.blocked, f"Gate closed incorrectly: {result.reason}"
    assert ErrorTrackingService.get_instance().get_warning_count() == 5


def test_scenario_error_threshold_closes_gate(temp_store: SQLiteClient) -> None:
    """Test that ERROR threshold closes gate."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    gate = FailedGate(store=temp_store)

    # Record 2 errors (threshold is 2 in 10 minutes)
    for i in range(2):
        ErrorTrackingService.get_instance().record_error(
            error_code="E_API_RATE_LIMIT",
            error_message=f"Error {i}",
        )

    # Gate should close
    result = gate.check()
    assert result.blocked
    assert "ERROR-severity threshold" in (result.reason or "")


def test_scenario_critical_immediate_close(temp_store: SQLiteClient) -> None:
    """Test that CRITICAL closes gate immediately."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    gate = FailedGate(store=temp_store)

    # Record 1 critical
    ErrorTrackingService.get_instance().record_error(
        error_code="E_MODEL_NOT_FOUND",
        error_message="Model not found",
    )

    # Gate should close immediately
    result = gate.check()
    assert result.blocked
    assert "CRITICAL" in (result.reason or "")


def test_scenario_mixed_severities(temp_store: SQLiteClient) -> None:
    """Test handling of mixed severity levels."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    gate = FailedGate(store=temp_store)

    # Record mixed severities
    ErrorTrackingService.get_instance().record_error(
        error_code="E_EXEC_NO_OUTPUT",  # WARNING
        error_message="Warning 1",
    )
    ErrorTrackingService.get_instance().record_error(
        error_code="E_API_RATE_LIMIT",  # ERROR
        error_message="Error 1",
    )
    ErrorTrackingService.get_instance().record_error(
        error_code="E_CAPACITY_SKIP",  # WARNING
        error_message="Warning 2",
    )

    # Gate should remain open (1 ERROR, threshold is 2)
    result = gate.check()
    assert not result.blocked

    # Verify counts
    status = ErrorTrackingService.get_instance().get_status()
    assert status["warning_count"] == 2
    assert status["error_count"] == 1
    assert status["critical_count"] == 0


def test_end_to_end_error_flow(temp_store: SQLiteClient) -> None:
    """Test complete error flow from recording to gate closure."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)
    gate = FailedGate(store=temp_store)

    # Start with no errors
    result = gate.check()
    assert not result.blocked

    # Record a warning - should not close gate
    ErrorTrackingService.get_instance().record_error(
        error_code="E_EXEC_NO_OUTPUT",
        error_message="No output from agent",
    )
    result = gate.check()
    assert not result.blocked

    # Record an ERROR - should not close gate yet (threshold is 2)
    ErrorTrackingService.get_instance().record_error(
        error_code="E_API_TIMEOUT",
        error_message="API timeout",
    )
    result = gate.check()
    assert not result.blocked

    # Record another ERROR - should close gate (threshold reached)
    ErrorTrackingService.get_instance().record_error(
        error_code="E_API_RATE_LIMIT",
        error_message="Rate limit",
    )
    result = gate.check()
    assert result.blocked
    assert "ERROR-severity threshold" in (result.reason or "")

    # Verify status shows correct breakdown
    status = ErrorTrackingService.get_instance().get_status()
    assert status["warning_count"] == 1
    assert status["error_count"] == 2
    assert status["critical_count"] == 0
