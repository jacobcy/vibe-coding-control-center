"""Tests for ErrorTrackingService cleanup functionality."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from vibe3.clients import SQLiteClient
from vibe3.exceptions.error_tracking import ErrorTrackingService


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


def test_cleanup_deletes_old_records(temp_store: SQLiteClient) -> None:
    """Cleanup should delete records older than retention period."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert old records (older than 7 days)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Old error 1', datetime('now', '-8 days'))
            """)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (2, 'E_API_RATE_LIMIT', 'Old error 2', datetime('now', '-10 days'))
            """)
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
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Recent error 1', datetime('now', '-1 day'))
            """)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (2, 'E_API_RATE_LIMIT', 'Recent error 2', datetime('now', '-3 days'))
            """)
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
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Old error', datetime('now', '-8 days'))
            """)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (2, 'E_API_RATE_LIMIT', 'Recent error', datetime('now', '-1 day'))
            """)
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
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (1, 'E_API_TIMEOUT', 'Old error', datetime('now', '-4 days'))
            """)
        # Should be preserved (within 3 days)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (2, 'E_API_RATE_LIMIT', 'Recent error', datetime('now', '-2 days'))
            """)
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
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, created_at)
            VALUES (3, 'E_API_ERROR', 'Old API error', datetime('now', '-15 minutes'))
            """)
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


def test_cleanup_terminal_deletes_done_aborted_stale(temp_store: SQLiteClient) -> None:
    """cleanup_terminal_issue_errors should delete errors for
    done/aborted/stale issues."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert flow_state records for issues with terminal status
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute("""
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES ('task/issue-100', 'test-flow-1', 'done', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES ('task/issue-200', 'test-flow-2', 'aborted', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES ('task/issue-300', 'test-flow-3', 'stale', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES ('task/issue-400', 'test-flow-4', 'active', datetime('now'))
        """)

        # Insert error records for each issue
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (1, 'E_API_TIMEOUT', 'Error for issue 100', 100)
        """)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (2, 'E_API_RATE_LIMIT', 'Error for issue 200', 200)
        """)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (3, 'E_API_ERROR', 'Error for issue 300', 300)
        """)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (4, 'E_API_TIMEOUT', 'Error for issue 400', 400)
        """)
        conn.commit()

    # Run cleanup
    deleted = ErrorTrackingService._instance.cleanup_terminal_issue_errors()

    # Verify deletion count (should delete 3 terminal issue errors)
    assert deleted == 3

    # Verify only active issue error remains
    with sqlite3.connect(temp_store.db_path) as conn:
        rows = conn.execute("SELECT issue_number FROM error_log").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 400


def test_cleanup_terminal_preserves_no_issue(temp_store: SQLiteClient) -> None:
    """cleanup_terminal_issue_errors should preserve errors with issue_number=NULL."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert error with NULL issue_number (governance error)
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (1, 'E_GOV_UNKNOWN', 'Governance error', NULL)
        """)
        conn.commit()

    # Run cleanup
    deleted = ErrorTrackingService._instance.cleanup_terminal_issue_errors()

    # Verify no deletion
    assert deleted == 0

    # Verify governance error is preserved
    with sqlite3.connect(temp_store.db_path) as conn:
        rows = conn.execute("SELECT error_code FROM error_log").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "E_GOV_UNKNOWN"


def test_cleanup_terminal_preserves_no_flow_record(temp_store: SQLiteClient) -> None:
    """cleanup_terminal_issue_errors should preserve errors for
    issues without flow_state."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert error for an issue that has no flow_state record
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (1, 'E_API_TIMEOUT', 'Error for issue 999', 999)
        """)
        conn.commit()

    # Run cleanup
    deleted = ErrorTrackingService._instance.cleanup_terminal_issue_errors()

    # Verify no deletion
    assert deleted == 0

    # Verify error is preserved
    with sqlite3.connect(temp_store.db_path) as conn:
        rows = conn.execute("SELECT issue_number FROM error_log").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 999


def test_cleanup_terminal_returns_correct_count(temp_store: SQLiteClient) -> None:
    """cleanup_terminal_issue_errors should return correct count of deleted records."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Insert flow_state records
    with sqlite3.connect(temp_store.db_path) as conn:
        conn.execute("""
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES ('task/issue-100', 'test-flow-1', 'done', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO flow_state (branch, flow_slug, flow_status, updated_at)
            VALUES ('task/issue-200', 'test-flow-2', 'active', datetime('now'))
        """)

        # Insert multiple errors for done issue (should be deleted)
        for i in range(3):
            conn.execute(
                """
                INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
                VALUES (?, 'E_API_TIMEOUT', 'Error for issue 100', 100)
            """,
                (i + 1,),
            )

        # Insert errors for active issue (should be preserved)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (4, 'E_API_RATE_LIMIT', 'Error for issue 200', 200)
        """)
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (5, 'E_API_ERROR', 'Another error for issue 200', 200)
        """)
        conn.commit()

    # Run cleanup
    deleted = ErrorTrackingService._instance.cleanup_terminal_issue_errors()

    # Verify count
    assert deleted == 3

    # Verify active issue errors are preserved
    with sqlite3.connect(temp_store.db_path) as conn:
        rows = conn.execute("SELECT issue_number FROM error_log").fetchall()
        assert len(rows) == 2
        assert all(row[0] == 200 for row in rows)


def test_cleanup_terminal_empty_table(temp_store: SQLiteClient) -> None:
    """cleanup_terminal_issue_errors should return 0 on empty error_log."""
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    # Run cleanup on empty table
    deleted = ErrorTrackingService._instance.cleanup_terminal_issue_errors()

    # Verify no deletion
    assert deleted == 0
