"""Tests for SQLite flow state repository bulk operations."""

import tempfile
from pathlib import Path

from vibe3.clients import SQLiteClient


def test_get_flow_state_bulk_returns_matching() -> None:
    """Bulk query should return matching flow states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Insert 3 flow states
        store.update_flow_state(
            "task/issue-100", flow_slug="issue-100", flow_status="active"
        )
        store.update_flow_state(
            "task/issue-200", flow_slug="issue-200", flow_status="active"
        )
        store.update_flow_state(
            "task/issue-300", flow_slug="issue-300", flow_status="active"
        )

        # Bulk query for 2 of them
        result = store.get_flow_state_bulk(["task/issue-100", "task/issue-300"])

        assert len(result) == 2
        assert "task/issue-100" in result
        assert "task/issue-300" in result
        assert result["task/issue-100"]["flow_status"] == "active"
        assert result["task/issue-300"]["flow_status"] == "active"


def test_get_flow_state_bulk_empty_input() -> None:
    """Bulk query with empty list should return empty dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        result = store.get_flow_state_bulk([])
        assert result == {}


def test_get_flow_state_bulk_excludes_deleted() -> None:
    """Bulk query should exclude soft-deleted flow states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Insert and soft-delete one flow
        store.update_flow_state(
            "task/issue-100", flow_slug="issue-100", flow_status="active"
        )
        store.soft_delete_flow("task/issue-100")

        # Insert another active flow
        store.update_flow_state(
            "task/issue-200", flow_slug="issue-200", flow_status="active"
        )

        # Bulk query both
        result = store.get_flow_state_bulk(["task/issue-100", "task/issue-200"])

        # Only active flow should be returned
        assert len(result) == 1
        assert "task/issue-200" in result
        assert "task/issue-100" not in result


def test_get_flows_by_issues_bulk_returns_grouped() -> None:
    """Bulk query should group flows by issue number."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flows and issue links
        store.update_flow_state(
            "task/issue-100", flow_slug="issue-100", flow_status="active"
        )
        store.update_flow_state(
            "task/issue-200", flow_slug="issue-200", flow_status="active"
        )

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("task/issue-100", 100, "task"),
        )
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("task/issue-200", 200, "task"),
        )
        conn.commit()

        # Bulk query both issues
        result = store.get_flows_by_issues_bulk([100, 200], role="task")

        assert len(result) == 2
        assert len(result[100]) == 1
        assert len(result[200]) == 1
        assert result[100][0]["branch"] == "task/issue-100"
        assert result[200][0]["branch"] == "task/issue-200"


def test_get_flows_by_issues_bulk_empty_input() -> None:
    """Bulk query with empty list should return empty dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        result = store.get_flows_by_issues_bulk([], role="task")
        assert result == {}


def test_get_flows_by_issues_bulk_missing_issue() -> None:
    """Bulk query should return empty list for missing issues."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create one issue-flow link
        store.update_flow_state(
            "task/issue-100", flow_slug="issue-100", flow_status="active"
        )

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("task/issue-100", 100, "task"),
        )
        conn.commit()

        # Query for both existing and missing issue
        result = store.get_flows_by_issues_bulk([100, 999], role="task")

        assert len(result) == 2
        assert len(result[100]) == 1
        assert result[999] == []
