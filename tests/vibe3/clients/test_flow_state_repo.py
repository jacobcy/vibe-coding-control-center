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


def test_get_branch_for_task_issue_returns_branch() -> None:
    """Get branch for task issue should return correct branch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow and issue link
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

        # Query for branch
        result = store.get_branch_for_task_issue(100)

        assert result == "task/issue-100"


def test_get_branch_for_task_issue_returns_none_for_missing() -> None:
    """Get branch for non-existent issue should return None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Query for non-existent issue
        result = store.get_branch_for_task_issue(999)

        assert result is None


def test_get_branch_for_task_issue_returns_none_for_non_task_role() -> None:
    """Get branch should not return dependency role links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow and issue link with dependency role
        store.update_flow_state(
            "task/issue-100", flow_slug="issue-100", flow_status="active"
        )
        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("task/issue-100", 100, "dependency"),
        )
        conn.commit()

        # Query for branch with task role
        result = store.get_branch_for_task_issue(100)

        # Should return None because link is 'dependency' not 'task'
        assert result is None


def test_list_invalid_branch_links_returns_empty_when_clean() -> None:
    """Scan should return empty list when no invalid branch links."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

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

        result = store.list_invalid_branch_links(
            scene_base_ref="origin/main",
            protected_branches=["main", "master", "develop"],
        )

        assert result == []


def test_list_invalid_branch_links_detects_main() -> None:
    """Scan should detect 'main' branch link."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("main", 100, "task"),
        )
        conn.commit()

        result = store.list_invalid_branch_links(
            scene_base_ref="origin/develop",
            protected_branches=["main"],
        )

        assert len(result) == 1
        assert result[0]["branch"] == "main"
        assert result[0]["issue_number"] == 100
        assert result[0]["issue_role"] == "task"


def test_list_invalid_branch_links_detects_master() -> None:
    """Scan should detect 'master' branch link."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("master", 100, "task"),
        )
        conn.commit()

        result = store.list_invalid_branch_links(
            scene_base_ref="origin/main",
            protected_branches=["master", "develop"],
        )

        assert len(result) == 1
        assert result[0]["branch"] == "master"


def test_list_invalid_branch_links_detects_develop() -> None:
    """Scan should detect 'develop' branch link."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("develop", 100, "task"),
        )
        conn.commit()

        result = store.list_invalid_branch_links(
            scene_base_ref="origin/main",
            protected_branches=["master", "develop"],
        )

        assert len(result) == 1
        assert result[0]["branch"] == "develop"


def test_list_invalid_branch_links_detects_origin_main() -> None:
    """Scan should detect 'origin/main' branch link."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("origin/main", 100, "task"),
        )
        conn.commit()

        result = store.list_invalid_branch_links(
            scene_base_ref="origin/develop",
            protected_branches=["main"],
        )

        assert len(result) == 1
        assert result[0]["branch"] == "origin/main"


def test_list_invalid_branch_links_detects_scene_base_ref() -> None:
    """Scan should detect configured scene_base_ref branch link."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("release/v1.0", 100, "task"),
        )
        conn.commit()

        result = store.list_invalid_branch_links(
            scene_base_ref="release/v1.0",
            protected_branches=["main"],
        )

        assert len(result) == 1
        assert result[0]["branch"] == "release/v1.0"


def test_delete_invalid_branch_links_removes_only_targeted() -> None:
    """Delete should remove only specified rows, leave valid ones."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("main", 100, "task"),
        )
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("task/issue-200", 200, "task"),
        )
        conn.commit()

        invalid_rows = [{"branch": "main", "issue_number": 100, "issue_role": "task"}]
        deleted_count = store.delete_invalid_branch_links(invalid_rows)

        assert deleted_count == 1

        cursor.execute("SELECT COUNT(*) FROM flow_issue_links WHERE branch = 'main'")
        assert cursor.fetchone()[0] == 0

        cursor.execute(
            "SELECT COUNT(*) FROM flow_issue_links WHERE branch = 'task/issue-200'"
        )
        assert cursor.fetchone()[0] == 1


def test_delete_invalid_branch_links_returns_delete_count() -> None:
    """Delete method should return correct count of deleted rows."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        conn = store._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("main", 100, "task"),
        )
        cursor.execute(
            "INSERT INTO flow_issue_links "
            "(branch, issue_number, issue_role, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("master", 200, "task"),
        )
        conn.commit()

        invalid_rows = [
            {"branch": "main", "issue_number": 100, "issue_role": "task"},
            {"branch": "master", "issue_number": 200, "issue_role": "task"},
        ]
        deleted_count = store.delete_invalid_branch_links(invalid_rows)

        assert deleted_count == 2
