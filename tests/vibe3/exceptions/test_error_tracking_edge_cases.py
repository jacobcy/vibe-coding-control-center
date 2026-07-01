"""Tests for ErrorTrackingService.get_all_errors_status() edge cases."""

import sqlite3

from vibe3.clients import SQLiteClient
from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService


def test_get_all_errors_status_empty_db(temp_store: SQLiteClient) -> None:
    """get_all_errors_status should return all zeros on empty database."""
    svc = ErrorTrackingService._registry[temp_store.db_path] = ErrorTrackingService(
        store=temp_store
    )

    status = svc.get_all_errors_status()

    assert status["total_errors"] == 0
    assert status["critical_count"] == 0
    assert status["error_count"] == 0
    assert status["warning_count"] == 0


def test_get_all_errors_status_single_severity(temp_store: SQLiteClient) -> None:
    """get_all_errors_status should count errors of a single severity."""
    svc = ErrorTrackingService._registry[temp_store.db_path] = ErrorTrackingService(
        store=temp_store
    )

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Insert 3 ERROR-severity records
    for i in range(3):
        svc.record_error(
            "E_API_RATE_LIMIT",
            f"Rate limit {i}",
            severity=ErrorSeverity.ERROR,
        )

    status = svc.get_all_errors_status()

    assert status["total_errors"] == 3
    assert status["error_count"] == 3
    assert status["critical_count"] == 0
    assert status["warning_count"] == 0


def test_get_all_errors_status_severity_buckets(temp_store: SQLiteClient) -> None:
    """get_all_errors_status should correctly bucket mixed severity levels."""
    svc = ErrorTrackingService._registry[temp_store.db_path] = ErrorTrackingService(
        store=temp_store
    )

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Insert 2 CRITICAL + 3 ERROR + 1 WARNING
    for i in range(2):
        svc.record_error(
            "E_MODEL_NOT_FOUND",
            f"Model error {i}",
            severity=ErrorSeverity.CRITICAL,
        )
    for i in range(3):
        svc.record_error(
            "E_API_RATE_LIMIT",
            f"Rate limit {i}",
            severity=ErrorSeverity.ERROR,
        )
    svc.record_error(
        "E_EXEC_NO_OUTPUT",
        "No output",
        severity=ErrorSeverity.WARNING,
    )

    status = svc.get_all_errors_status()

    assert status["critical_count"] == 2
    assert status["error_count"] == 3
    assert status["warning_count"] == 1
    assert status["total_errors"] == 6
    assert (
        status["critical_count"] + status["error_count"] + status["warning_count"]
        == status["total_errors"]
    )


def test_get_all_errors_status_null_severity_via_service_defaults_to_error(
    temp_store: SQLiteClient,
) -> None:
    """get_all_errors_status via service method should count NULL severity as ERROR."""
    svc = ErrorTrackingService._registry[temp_store.db_path] = ErrorTrackingService(
        store=temp_store
    )

    # Insert row with NULL severity via raw SQL (omitting severity column)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message)
            VALUES (1, 'E_CUSTOM_ERROR', 'Error without severity')
        """
        )
        conn.commit()

    status = svc.get_all_errors_status()

    # NULL severity should be counted as ERROR
    assert status["error_count"] == 1
    assert status["total_errors"] == 1
    assert status["critical_count"] == 0
    assert status["warning_count"] == 0


def test_get_all_errors_status_ignores_time_window(temp_store: SQLiteClient) -> None:
    """get_all_errors_status should count all errors regardless of time window."""
    svc = ErrorTrackingService._registry[temp_store.db_path] = ErrorTrackingService(
        store=temp_store
    )

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Insert recent error (within window)
    svc.record_error(
        "E_API_RATE_LIMIT",
        "Recent error",
        severity=ErrorSeverity.ERROR,
    )

    # Insert old error outside window (>10 min)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log
            (tick_id, error_code, error_message, severity, created_at)
            VALUES (
                2, 'E_API_TIMEOUT', 'Old error', 'ERROR',
                datetime('now', '-15 minutes')
            )
        """
        )
        conn.commit()

    # get_all_errors_status should count BOTH errors (no time filter)
    all_status = svc.get_all_errors_status()
    assert all_status["total_errors"] == 2

    # get_status (windowed) should only count recent error
    windowed_status = svc.get_status()
    assert windowed_status["total_errors"] == 1
