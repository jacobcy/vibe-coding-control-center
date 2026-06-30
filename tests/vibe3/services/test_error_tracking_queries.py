"""Tests for error_tracking/queries.py pure query functions."""

from __future__ import annotations

import sqlite3

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.orchestra.error_tracking.queries import (
    has_recent_specific_error,
)


@pytest.fixture
def error_log_db(tmp_path) -> SQLiteClient:
    """Create a temporary database with error_log table initialized."""
    from vibe3.clients.sqlite_schema import init_schema

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    init_schema(conn)
    conn.close()
    return SQLiteClient(db_path=str(db_path))


def insert_error(
    db_path: str,
    error_code: str,
    issue_number: int | None = None,
    branch: str | None = None,
    minutes_ago: int = 0,
) -> None:
    """Helper to insert an error record using SQLite's own time functions."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO error_log
            (tick_id, error_code, error_message, severity, issue_number,
             branch, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', ? || ' minutes'))
            """,
            (
                1,
                error_code,
                f"Test error: {error_code}",
                "ERROR",
                issue_number or 0,
                branch or "",
                f"-{minutes_ago}",
            ),
        )


class TestHasRecentSpecificError:
    """Tests for has_recent_specific_error query function."""

    def test_returns_true_when_matching_error_exists(
        self, error_log_db: SQLiteClient
    ) -> None:
        """Recent specific error matching issue/branch should return True."""
        insert_error(
            error_log_db.db_path,
            error_code="E_MODEL_CONFIG",
            issue_number=123,
            branch="test-branch",
            minutes_ago=0,
        )

        result = has_recent_specific_error(
            error_log_db.db_path,
            issue_number=123,
            branch="test-branch",
            within_seconds=60,
        )
        assert result is True

    def test_returns_false_when_window_exceeded(
        self, error_log_db: SQLiteClient
    ) -> None:
        """Error older than window should return False."""
        insert_error(
            error_log_db.db_path,
            error_code="E_MODEL_CONFIG",
            issue_number=123,
            branch="test-branch",
            minutes_ago=5,  # 300 seconds ago, exceeds 60s window
        )

        result = has_recent_specific_error(
            error_log_db.db_path,
            issue_number=123,
            branch="test-branch",
            within_seconds=60,
        )
        assert result is False

    def test_returns_false_for_excluded_codes(self, error_log_db: SQLiteClient) -> None:
        """E_DISPATCH_FAILURE and E_DISPATCH_CODE_ERROR should be excluded."""
        insert_error(
            error_log_db.db_path,
            error_code="E_DISPATCH_FAILURE",
            issue_number=123,
            branch="test-branch",
            minutes_ago=0,
        )
        insert_error(
            error_log_db.db_path,
            error_code="E_DISPATCH_CODE_ERROR",
            issue_number=123,
            branch="test-branch",
            minutes_ago=0,
        )

        result = has_recent_specific_error(
            error_log_db.db_path,
            issue_number=123,
            branch="test-branch",
            within_seconds=60,
        )
        assert result is False

    def test_returns_false_for_issue_number_mismatch(
        self, error_log_db: SQLiteClient
    ) -> None:
        """Different issue_number should return False."""
        insert_error(
            error_log_db.db_path,
            error_code="E_MODEL_CONFIG",
            issue_number=456,  # Different issue
            branch="test-branch",
            minutes_ago=0,
        )

        result = has_recent_specific_error(
            error_log_db.db_path,
            issue_number=123,  # Querying for different issue
            branch="test-branch",
            within_seconds=60,
        )
        assert result is False

    def test_returns_false_for_branch_mismatch(
        self, error_log_db: SQLiteClient
    ) -> None:
        """Different branch should return False."""
        insert_error(
            error_log_db.db_path,
            error_code="E_MODEL_CONFIG",
            issue_number=123,
            branch="other-branch",  # Different branch
            minutes_ago=0,
        )

        result = has_recent_specific_error(
            error_log_db.db_path,
            issue_number=123,
            branch="test-branch",  # Querying for different branch
            within_seconds=60,
        )
        assert result is False

    def test_returns_false_on_db_error(self, tmp_path) -> None:
        """Return False conservatively if query fails."""
        # Use a path that doesn't exist to trigger exception
        invalid_path = str(tmp_path / "nonexistent.db")
        result = has_recent_specific_error(
            invalid_path,
            issue_number=123,
            branch="test-branch",
            within_seconds=60,
        )
        assert result is False

    def test_custom_excluded_codes(self, error_log_db: SQLiteClient) -> None:
        """Custom excluded_codes parameter should be honored."""
        insert_error(
            error_log_db.db_path,
            error_code="E_CUSTOM_EXCLUDE",
            issue_number=123,
            branch="test-branch",
            minutes_ago=0,
        )

        # Exclude E_CUSTOM_EXCLUDE
        result = has_recent_specific_error(
            error_log_db.db_path,
            issue_number=123,
            branch="test-branch",
            within_seconds=60,
            excluded_codes=("E_CUSTOM_EXCLUDE",),
        )
        assert result is False

        # Without exclusion, should return True
        result = has_recent_specific_error(
            error_log_db.db_path,
            issue_number=123,
            branch="test-branch",
            within_seconds=60,
            excluded_codes=(),  # No exclusions
        )
        assert result is True
