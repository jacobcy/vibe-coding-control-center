"""Regression tests for Vibe3 test database isolation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.error_helpers import record_error
from vibe3.services.error_tracking_service import ErrorTrackingService


def test_default_sqlite_client_uses_isolated_database(isolate_database: Path) -> None:
    """Default SQLiteClient should derive handoff.db inside the test tempdir."""
    store = SQLiteClient()

    expected_db_path = isolate_database / "vibe3" / "handoff.db"
    assert Path(store.db_path) == expected_db_path
    assert expected_db_path.exists()


def test_default_error_tracking_singleton_uses_isolated_database(
    isolate_database: Path,
) -> None:
    """record_error(store=None) should not reuse a stale non-isolated singleton."""
    record_error(
        error_code="E_EXEC_UNKNOWN",
        error_message="isolation regression marker",
        issue_number=1857,
        branch="test/database-isolation",
    )

    expected_db_path = isolate_database / "vibe3" / "handoff.db"
    instance = ErrorTrackingService.get_instance()
    assert Path(instance.db_path) == expected_db_path

    with sqlite3.connect(expected_db_path) as conn:
        count = conn.execute(
            """
            SELECT COUNT(*) FROM error_log
            WHERE issue_number = ?
              AND branch = ?
              AND error_message = ?
            """,
            (1857, "test/database-isolation", "isolation regression marker"),
        ).fetchone()[0]

    assert count == 1
