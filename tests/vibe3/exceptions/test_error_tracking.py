"""Tests for ErrorTrackingService cleanup functionality."""

import sqlite3
from pathlib import Path

import pytest

from vibe3.clients import SQLiteClient
from vibe3.services.orchestra.error_tracking.service import ErrorTrackingService


def test_cleanup_deletes_old_records(temp_store: SQLiteClient) -> None:
    """Cleanup should delete records older than retention period."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert old records (older than 7 days)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Old error 1', datetime('now', '-8 days'))
            """
        )
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (2, 'E_API_RATE_LIMIT', 'Old error 2', datetime('now', '-10 days'))
            """
        )
        conn.commit()

    # Run cleanup
    deleted = ErrorTrackingService._instance.cleanup_old_errors()

    # Verify deletion
    assert deleted == 2

    # Verify database state
    with sqlite3.connect(temp_store.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM error_log").fetchone()[0]
        assert count == 0


def test_cleanup_empty_table_returns_zero(temp_store: SQLiteClient) -> None:
    """Cleanup should be a no-op on an empty error log."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    assert ErrorTrackingService._instance.cleanup_old_errors() == 0


def test_cleanup_preserves_recent_records(temp_store: SQLiteClient) -> None:
    """Cleanup should preserve records within retention period."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert recent records (within 7 days)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Recent error 1', datetime('now', '-1 day'))
            """
        )
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (2, 'E_API_RATE_LIMIT', 'Recent error 2', datetime('now', '-3 days'))
            """
        )
        conn.commit()

    # Run cleanup
    deleted = ErrorTrackingService._instance.cleanup_old_errors()

    # Verify no deletion
    assert deleted == 0

    # Verify database state
    with sqlite3.connect(temp_store.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM error_log").fetchone()[0]
        assert count == 2


def test_cleanup_returns_correct_count(temp_store: SQLiteClient) -> None:
    """Cleanup should return the correct number of deleted records."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert mixed records (old and new)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Old error', datetime('now', '-8 days'))
            """
        )
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (2, 'E_API_RATE_LIMIT', 'Recent error', datetime('now', '-1 day'))
            """
        )
        conn.commit()

    # Run cleanup
    deleted = ErrorTrackingService._instance.cleanup_old_errors()

    # Verify count
    assert deleted == 1

    # Verify database state
    with sqlite3.connect(temp_store.db_path) as conn:
        rows = conn.execute(
            "SELECT error_code FROM error_log ORDER BY created_at"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "E_API_RATE_LIMIT"


def test_cleanup_with_custom_retention(temp_store: SQLiteClient) -> None:
    """Cleanup should respect custom retention_days value."""
    # Create service with 3-day retention
    ErrorTrackingService._instance = ErrorTrackingService(
        store=temp_store, retention_days=3
    )

    # Insert records
    with sqlite3.connect(temp_store.db_path) as conn:
        # Should be deleted (older than 3 days)
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Old error', datetime('now', '-4 days'))
            """
        )
        # Should be preserved (within 3 days)
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (2, 'E_API_RATE_LIMIT', 'Recent error', datetime('now', '-2 days'))
            """
        )
        conn.commit()

    # Run cleanup with 3-day retention
    deleted = ErrorTrackingService._instance.cleanup_old_errors()

    # Verify deletion
    assert deleted == 1

    # Verify database state
    with sqlite3.connect(temp_store.db_path) as conn:
        rows = conn.execute("SELECT error_code FROM error_log").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "E_API_RATE_LIMIT"


@pytest.mark.parametrize("retention_days", [0, -1])
def test_retention_days_must_be_positive(
    temp_store: SQLiteClient, retention_days: int
) -> None:
    """Retention period must be positive to avoid destructive cleanup settings."""
    with pytest.raises(ValueError, match="retention_days must be positive"):
        ErrorTrackingService(store=temp_store, retention_days=retention_days)


def test_cleanup_does_not_affect_threshold_detection(
    temp_store: SQLiteClient,
) -> None:
    """Cleanup should not affect API error threshold detection in 10-minute window."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert recent API errors (within 10 minutes)
    ErrorTrackingService._instance.record_error("E_API_TIMEOUT", "Recent API error 1")
    ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT", "Recent API error 2"
    )

    # Insert old API error (outside threshold window but within retention)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (3, 'E_API_ERROR', 'Old API error', datetime('now', '-15 minutes'))
            """
        )
        conn.commit()

    # Verify threshold detection before cleanup
    api_count_before = ErrorTrackingService._instance.get_api_error_count()
    assert api_count_before == 2  # Only count recent errors (10-minute window)

    # Run cleanup (should not delete any records, all within 7-day retention)
    deleted = ErrorTrackingService._instance.cleanup_old_errors()
    assert deleted == 0

    # Verify threshold detection after cleanup
    api_count_after = ErrorTrackingService._instance.get_api_error_count()
    assert api_count_after == 2  # Still same count


def test_get_status_category_sums_match_total(temp_store: SQLiteClient) -> None:
    """get_status() should count actual errors, not unique error codes."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Record errors with duplicate codes
    for _ in range(3):
        ErrorTrackingService._instance.record_error("E_API_RATE_LIMIT", "Rate limit")
    for _ in range(5):
        ErrorTrackingService._instance.record_error(
            "E_EXEC_UNKNOWN", "Unknown exec error"
        )
    for _ in range(2):
        ErrorTrackingService._instance.record_error("E_EXEC_NO_OUTPUT", "No output")

    status = ErrorTrackingService._instance.get_status()

    # Verify category sums match total
    assert status["total_errors"] == 10
    assert status["model_errors"] == 0
    assert status["api_errors"] == 3
    assert status["exec_errors"] == 7
    assert (
        status["model_errors"] + status["api_errors"] + status["exec_errors"]
        == status["total_errors"]
    )


def test_record_error_minimal_call(temp_store: SQLiteClient) -> None:
    """record_error should work with only required parameters."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Call with minimal parameters (WARNING-severity error, no threshold)
    threshold_reached, error_count = ErrorTrackingService._instance.record_error(
        "E_EXEC_NO_OUTPUT", "Test message"  # WARNING severity in registry
    )

    # Verify return values (WARNING errors don't trigger threshold)
    assert threshold_reached is False
    assert error_count == 0

    # Verify database state - record should be persisted
    with sqlite3.connect(temp_store.db_path) as conn:
        row = conn.execute(
            """
            SELECT tick_id, error_code, error_message, issue_number, branch, severity
            FROM error_log
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        assert row is not None
        assert row[0] == 0  # tick_id defaults to 0
        assert row[1] == "E_EXEC_NO_OUTPUT"
        assert row[2] == "Test message"
        assert row[3] is None  # issue_number is NULL
        assert row[4] is None  # branch is NULL
        assert row[5] == "WARNING"  # severity inferred from registry


def test_record_error_tick_only(temp_store: SQLiteClient) -> None:
    """record_error should work with tick_id but no issue_number/branch."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Call with tick_id only (mirrors governance_sync_runner usage)
    # Using WARNING-severity error to test non-threshold case
    threshold_reached, error_count = ErrorTrackingService._instance.record_error(
        "E_EXEC_NO_OUTPUT", "Test message", tick_id=42
    )

    # Verify return values (WARNING errors don't trigger threshold)
    assert threshold_reached is False
    assert error_count == 0

    # Verify database state - record should be persisted
    with sqlite3.connect(temp_store.db_path) as conn:
        row = conn.execute(
            """
            SELECT tick_id, error_code, error_message, issue_number, branch, severity
            FROM error_log
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        assert row is not None
        assert row[0] == 42  # tick_id preserved
        assert row[1] == "E_EXEC_NO_OUTPUT"
        assert row[2] == "Test message"
        assert row[3] is None  # issue_number is NULL
        assert row[4] is None  # branch is NULL
        assert row[5] == "WARNING"  # severity inferred from registry


# Tests for severity-aware tracking (Task 3)


def test_record_error_with_explicit_severity(temp_store: SQLiteClient) -> None:
    """record_error should accept severity parameter and store it."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Import here to avoid circular dependency
    from vibe3.exceptions.error_severity import ErrorSeverity

    # Record error with explicit severity
    threshold_reached, error_count = ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT",
        "Rate limit exceeded",
        severity=ErrorSeverity.ERROR,
    )

    # Verify severity stored in database
    with sqlite3.connect(temp_store.db_path) as conn:
        row = conn.execute(
            """
            SELECT error_code, severity
            FROM error_log
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "E_API_RATE_LIMIT"
        assert row[1] == "ERROR"


def test_record_error_infers_severity_from_registry(
    temp_store: SQLiteClient,
) -> None:
    """record_error should infer severity from error registry when not provided."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Import here to avoid circular dependency

    # Record error without severity (should infer from registry)
    ErrorTrackingService._instance.record_error(
        "E_MODEL_NOT_FOUND",  # CRITICAL in registry
        "Model not found",
    )

    # Verify severity inferred correctly
    with sqlite3.connect(temp_store.db_path) as conn:
        row = conn.execute(
            """
            SELECT error_code, severity
            FROM error_log
            ORDER BY created_at DESC LIMIT 1
            """
        ).fetchone()
        assert row is not None
        assert row[0] == "E_MODEL_NOT_FOUND"
        assert row[1] == "CRITICAL"  # Inferred from registry


def test_get_threshold_error_count_counts_error_severity(
    temp_store: SQLiteClient,
) -> None:
    """get_threshold_error_count should count only ERROR-severity errors."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Record errors of different severities
    ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT",
        "Rate limit",
        severity=ErrorSeverity.ERROR,
    )
    ErrorTrackingService._instance.record_error(
        "E_API_TIMEOUT",
        "Timeout",
        severity=ErrorSeverity.ERROR,
    )
    ErrorTrackingService._instance.record_error(
        "E_MODEL_NOT_FOUND",
        "Model error",
        severity=ErrorSeverity.CRITICAL,
    )
    ErrorTrackingService._instance.record_error(
        "E_EXEC_NO_OUTPUT",
        "No output",
        severity=ErrorSeverity.WARNING,
    )

    # Count should only include ERROR-severity errors
    count = ErrorTrackingService._instance.get_threshold_error_count()
    assert count == 2  # Only ERROR, not CRITICAL or WARNING


def test_get_warning_count_counts_warning_severity(temp_store: SQLiteClient) -> None:
    """get_warning_count should count only WARNING-severity errors."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Record errors of different severities
    ErrorTrackingService._instance.record_error(
        "E_EXEC_NO_OUTPUT",
        "No output 1",
        severity=ErrorSeverity.WARNING,
    )
    ErrorTrackingService._instance.record_error(
        "E_EXEC_NO_OUTPUT",
        "No output 2",
        severity=ErrorSeverity.WARNING,
    )
    ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT",
        "Rate limit",
        severity=ErrorSeverity.ERROR,
    )

    # Count should only include WARNING-severity errors
    count = ErrorTrackingService._instance.get_warning_count()
    assert count == 2


def test_threshold_count_uses_severity_not_prefix(temp_store: SQLiteClient) -> None:
    """Threshold counting should be by severity, not error code prefix."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Record a custom error code with ERROR severity
    ErrorTrackingService._instance.record_error(
        "E_CUSTOM_ERROR",  # Not E_API_* or E_EXEC_*
        "Custom error",
        severity=ErrorSeverity.ERROR,
    )

    # Should be counted by severity
    count = ErrorTrackingService._instance.get_threshold_error_count()
    assert count == 1


def test_threshold_count_respects_time_window(temp_store: SQLiteClient) -> None:
    """get_threshold_error_count should respect time window."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Record recent error
    ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT",
        "Recent",
        severity=ErrorSeverity.ERROR,
    )

    # Insert old error outside window
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log
            (tick_id, error_code, error_message, severity, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Old', 'ERROR', datetime('now', '-15 minutes'))
        """
        )
        conn.commit()

    # Count should only include recent error
    count = ErrorTrackingService._instance.get_threshold_error_count()
    assert count == 1


def test_migration_backfills_severity_column(tmp_path: Path) -> None:
    """Migration should add severity column and backfill from error registry."""
    from vibe3.clients.sqlite_schema import init_schema

    # Create database WITHOUT severity column
    db_path = tmp_path / "migration_test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create error_log table without severity column (pre-migration schema)
    cursor.execute(
        """
        CREATE TABLE error_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tick_id INTEGER NOT NULL,
            error_code TEXT NOT NULL,
            error_message TEXT NOT NULL,
            issue_number INTEGER,
            branch TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """
    )

    # Insert error records with known error codes
    cursor.execute(
        """
        INSERT INTO error_log (tick_id, error_code, error_message)
        VALUES (1, 'E_MODEL_NOT_FOUND', 'Model not found')
    """
    )
    cursor.execute(
        """
        INSERT INTO error_log (tick_id, error_code, error_message)
        VALUES (2, 'E_API_RATE_LIMIT', 'Rate limit')
    """
    )
    cursor.execute(
        """
        INSERT INTO error_log (tick_id, error_code, error_message)
        VALUES (3, 'E_EXEC_NO_OUTPUT', 'No output')
    """
    )
    conn.commit()

    # Verify severity column does NOT exist
    columns_before = {
        row[1] for row in cursor.execute("PRAGMA table_info(error_log)").fetchall()
    }
    assert "severity" not in columns_before

    # Run init_schema() which should add severity column and backfill
    init_schema(conn)

    # Verify severity column exists
    columns_after = {
        row[1] for row in cursor.execute("PRAGMA table_info(error_log)").fetchall()
    }
    assert "severity" in columns_after

    # Verify severity values are populated from error registry
    rows = cursor.execute(
        """
        SELECT error_code, severity FROM error_log ORDER BY tick_id
    """
    ).fetchall()

    assert len(rows) == 3
    # E_MODEL_NOT_FOUND → CRITICAL
    assert rows[0] == ("E_MODEL_NOT_FOUND", "CRITICAL")
    # E_API_RATE_LIMIT → ERROR
    assert rows[1] == ("E_API_RATE_LIMIT", "ERROR")
    # E_EXEC_NO_OUTPUT → WARNING
    assert rows[2] == ("E_EXEC_NO_OUTPUT", "WARNING")

    conn.close()


# Tests for get_all_errors_status() - Issue #1331


def test_get_all_errors_status_total_includes_unknown_severity(
    temp_store: SQLiteClient,
) -> None:
    """get_all_errors_status() should count ALL severity values in total_errors."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Insert known severity errors via service
    ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT", "Error 1", severity=ErrorSeverity.ERROR
    )
    ErrorTrackingService._instance.record_error(
        "E_EXEC_NO_OUTPUT", "Warning 1", severity=ErrorSeverity.WARNING
    )

    # Insert unknown severity error via direct SQL (simulating future severity values)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, severity)
            VALUES (1, 'E_CUSTOM', 'Info severity error', 'INFO')
        """
        )
        conn.commit()

    # Call get_all_errors_status via the query function
    from vibe3.services.orchestra.error_tracking.queries import get_all_errors_status

    status = get_all_errors_status(temp_store.db_path)

    # total_errors should include ALL severity values
    assert status["total_errors"] == 3  # 1 ERROR + 1 WARNING + 1 INFO
    assert status["error_count"] == 1
    assert status["warning_count"] == 1
    # Unknown severity should be surfaced
    assert status["unknown_severity_counts"] == {"INFO": 1}


def test_get_all_errors_status_null_severity_defaults_to_error(
    temp_store: SQLiteClient,
) -> None:
    """NULL severity should be counted under ERROR (existing behavior preserved)."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert row with NULL severity via direct SQL
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log (tick_id, error_code, error_message, severity)
            VALUES (1, 'E_CUSTOM', 'Null severity', NULL)
        """
        )
        conn.commit()

    from vibe3.services.orchestra.error_tracking.queries import get_all_errors_status

    status = get_all_errors_status(temp_store.db_path)

    # NULL severity should be treated as ERROR
    assert status["total_errors"] == 1
    assert status["error_count"] == 1
    assert status["unknown_severity_counts"] == {}


def test_get_all_errors_status_no_unknown_severity_returns_empty_dict(
    temp_store: SQLiteClient,
) -> None:
    """When no unknown severities exist, unknown_severity_counts should be empty."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    from vibe3.exceptions.error_severity import ErrorSeverity

    # Insert only known severity errors
    ErrorTrackingService._instance.record_error(
        "E_MODEL_NOT_FOUND", "Critical", severity=ErrorSeverity.CRITICAL
    )
    ErrorTrackingService._instance.record_error(
        "E_API_RATE_LIMIT", "Error", severity=ErrorSeverity.ERROR
    )
    ErrorTrackingService._instance.record_error(
        "E_EXEC_NO_OUTPUT", "Warning", severity=ErrorSeverity.WARNING
    )

    from vibe3.services.orchestra.error_tracking.queries import get_all_errors_status

    status = get_all_errors_status(temp_store.db_path)

    # All severities are known
    assert status["total_errors"] == 3
    assert status["critical_count"] == 1
    assert status["error_count"] == 1
    assert status["warning_count"] == 1
    assert status["unknown_severity_counts"] == {}
