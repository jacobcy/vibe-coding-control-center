"""Tests for ErrorTrackingService terminal issue cleanup functionality."""

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

        # Link issues to their flows (issue_role='task')
        conn.execute("""
            INSERT INTO flow_issue_links (branch, issue_number, issue_role, created_at)
            VALUES ('task/issue-100', 100, 'task', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO flow_issue_links (branch, issue_number, issue_role, created_at)
            VALUES ('task/issue-200', 200, 'task', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO flow_issue_links (branch, issue_number, issue_role, created_at)
            VALUES ('task/issue-300', 300, 'task', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO flow_issue_links (branch, issue_number, issue_role, created_at)
            VALUES ('task/issue-400', 400, 'task', datetime('now'))
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

        # Link issues to their flows (issue_role='task')
        conn.execute("""
            INSERT INTO flow_issue_links (branch, issue_number, issue_role, created_at)
            VALUES ('task/issue-100', 100, 'task', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO flow_issue_links (branch, issue_number, issue_role, created_at)
            VALUES ('task/issue-200', 200, 'task', datetime('now'))
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


def test_cleanup_terminal_preserves_issue_with_active_new_flow(
    temp_store: SQLiteClient,
) -> None:
    """cleanup_terminal_issue_errors should preserve errors when issue has
    a superseded terminal flow but current task flow is active.

    Scenario: issue-100 has two flows:
    - Old task/issue-100 flow (terminal, soft-deleted)
    - New task/issue-100-v2 flow (active, current via flow_issue_links)

    Errors for issue-100 should NOT be deleted because the current task
    flow is active.
    """
    ErrorTrackingService._instance = ErrorTrackingService(store=temp_store)

    with sqlite3.connect(temp_store.db_path) as conn:
        # Insert superseded flow (terminal, soft-deleted)
        conn.execute("""
            INSERT INTO flow_state
                (branch, flow_slug, flow_status, deleted_at, updated_at)
            VALUES
                ('task/issue-100', 'old-flow', 'done', datetime('now'), datetime('now'))
        """)

        # Insert current active flow
        conn.execute("""
            INSERT INTO flow_state
                (branch, flow_slug, flow_status, updated_at)
            VALUES
                ('task/issue-100-v2', 'new-flow', 'active', datetime('now'))
        """)

        # Link issue to current active flow (issue_role='task')
        conn.execute("""
            INSERT INTO flow_issue_links
                (branch, issue_number, issue_role, created_at)
            VALUES
                ('task/issue-100-v2', 100, 'task', datetime('now'))
        """)

        # Insert error for issue-100
        conn.execute("""
            INSERT INTO error_log (tick_id, error_code, error_message, issue_number)
            VALUES (1, 'E_API_TIMEOUT', 'Error for issue 100', 100)
        """)
        conn.commit()

    # Run cleanup
    deleted = ErrorTrackingService._instance.cleanup_terminal_issue_errors()

    # Verify no deletion (current task flow is active)
    assert deleted == 0

    # Verify error is preserved
    with sqlite3.connect(temp_store.db_path) as conn:
        rows = conn.execute("SELECT issue_number FROM error_log").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 100
