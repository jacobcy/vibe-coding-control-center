"""Integration tests for IssueTitleCacheService with real SQLite."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.issue_title_cache_service import IssueTitleCacheService


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = sqlite3.connect(str(db_path))
        # Create schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flow_context_cache (
                branch TEXT PRIMARY KEY,
                task_issue_number INTEGER,
                issue_title TEXT,
                pr_number INTEGER,
                pr_title TEXT,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
        yield str(db_path)


class TestIssueTitleCacheIntegration:
    """Integration tests with real SQLite."""

    def test_branch_based_lookup(self, temp_db):
        """Verify lookup is done via branch (primary key)."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Insert test data
        cursor.execute("""
            INSERT INTO flow_context_cache
            (branch, task_issue_number, issue_title, pr_number, pr_title, updated_at)
            VALUES ('task/issue-123', 123, 'Test', NULL, NULL, '2024-01-01')
        """)
        conn.commit()

        # Verify lookup works
        cursor.execute(
            "SELECT * FROM flow_context_cache WHERE branch = ?", ("task/issue-123",)
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "task/issue-123"
        assert row[1] == 123
        assert row[2] == "Test"

        conn.close()

    def test_cache_service_with_real_db(self, temp_db):
        """Test IssueTitleCacheService with real SQLite database."""
        # Create SQLiteClient with temp db
        store = SQLiteClient(db_path=temp_db)

        # Create cache service without GitHub client (offline mode)
        service = IssueTitleCacheService(store, github_client=None)

        # Insert test data
        store.upsert_flow_context_cache(
            branch="task/issue-456",
            task_issue_number=456,
            issue_title="Test Issue 456",
            pr_number=None,
            pr_title=None,
        )

        # Test get_title
        title = service.get_title("task/issue-456")
        assert title == "Test Issue 456"

        # Test get_titles
        titles = service.get_titles(["task/issue-456", "task/issue-789"])
        assert titles == {"task/issue-456": "Test Issue 456"}

    def test_update_title_persists(self, temp_db):
        """Test that update_title persists to database."""
        store = SQLiteClient(db_path=temp_db)
        service = IssueTitleCacheService(store, github_client=None)

        # Create initial entry
        store.upsert_flow_context_cache(
            branch="task/issue-789",
            task_issue_number=789,
            issue_title="Old Title",
            pr_number=None,
            pr_title=None,
        )

        # Update title
        service.update_title("task/issue-789", "New Title")

        # Verify persistence
        cache = store.get_flow_context_cache("task/issue-789")
        assert cache is not None
        assert cache["issue_title"] == "New Title"
        assert cache["task_issue_number"] == 789

    def test_invalidate_clears_title(self, temp_db):
        """Test that invalidate clears the title."""
        store = SQLiteClient(db_path=temp_db)
        service = IssueTitleCacheService(store, github_client=None)

        # Create entry with title
        store.upsert_flow_context_cache(
            branch="task/issue-999",
            task_issue_number=999,
            issue_title="Title to Clear",
            pr_number=42,
            pr_title="PR Title",
        )

        # Invalidate
        service.invalidate("task/issue-999")

        # Verify title is cleared
        cache = store.get_flow_context_cache("task/issue-999")
        assert cache is not None
        assert cache["issue_title"] is None
        assert cache["task_issue_number"] == 999
        assert cache["pr_number"] == 42
        assert cache["pr_title"] == "PR Title"

    def test_get_title_with_fallback_no_github_client(self, temp_db):
        """Test get_title_with_fallback when cache miss and no GitHub client.

        Note: The service will lazy-initialize a GitHub client if not provided,
        so this test only verifies the cache-hit path works correctly.
        """
        store = SQLiteClient(db_path=temp_db)
        service = IssueTitleCacheService(store, github_client=None)

        # Create entry WITH title (cache hit)
        store.upsert_flow_context_cache(
            branch="task/issue-111",
            task_issue_number=111,
            issue_title="Cached Title",
            pr_number=None,
            pr_title=None,
        )

        # Should return cached title, no network error
        title, error = service.get_title_with_fallback("task/issue-111")
        assert title == "Cached Title"
        assert error is False

    def test_branch_is_primary_key(self, temp_db):
        """Verify that branch is indeed the primary key."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Get table info
        cursor.execute("PRAGMA table_info(flow_context_cache)")
        columns = cursor.fetchall()

        # Find primary key column
        pk_columns = [col for col in columns if col[5] == 1]  # pk flag is at index 5
        assert len(pk_columns) == 1
        assert pk_columns[0][1] == "branch"  # column name is at index 1

        conn.close()

    def test_multiple_branches_same_issue(self, temp_db):
        """Test handling multiple branches for the same issue."""
        store = SQLiteClient(db_path=temp_db)
        service = IssueTitleCacheService(store, github_client=None)

        # Create two branches for the same issue
        store.upsert_flow_context_cache(
            branch="task/issue-222",
            task_issue_number=222,
            issue_title="Title from task branch",
            pr_number=None,
            pr_title=None,
        )

        store.upsert_flow_context_cache(
            branch="dev/issue-222",
            task_issue_number=222,
            issue_title="Title from dev branch",
            pr_number=None,
            pr_title=None,
        )

        # Each branch should have its own title
        title1 = service.get_title("task/issue-222")
        title2 = service.get_title("dev/issue-222")

        assert title1 == "Title from task branch"
        assert title2 == "Title from dev branch"
