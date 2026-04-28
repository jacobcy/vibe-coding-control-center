"""Tests for flow context cache store."""

import tempfile
from pathlib import Path

from vibe3.clients import SQLiteClient


def test_flow_context_cache_roundtrip() -> None:
    """Cache store should support upsert and retrieval."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Upsert cache entry
        store.upsert_flow_context_cache(
            branch="task/issue-436",
            task_issue_number=436,
            issue_title="Manager cannot start after refactor",
            pr_number=512,
            pr_title="Fix orchestra async startup recursion",
        )

        # Retrieve cache
        row = store.get_flow_context_cache("task/issue-436")
        assert row is not None, "Cache entry should exist"
        assert row["task_issue_number"] == 436
        assert row["issue_title"] == "Manager cannot start after refactor"
        assert row["pr_number"] == 512
        assert row["pr_title"] == "Fix orchestra async startup recursion"


def test_cache_upsert_is_idempotent() -> None:
    """Cache upsert should replace existing entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # First upsert
        store.upsert_flow_context_cache(
            branch="task/issue-436",
            task_issue_number=436,
            issue_title="Old title",
            pr_number=None,
            pr_title=None,
        )

        # Second upsert (should replace)
        store.upsert_flow_context_cache(
            branch="task/issue-436",
            task_issue_number=436,
            issue_title="New title",
            pr_number=512,
            pr_title="Fix recursion",
        )

        # Verify replacement
        row = store.get_flow_context_cache("task/issue-436")
        assert row is not None
        assert row["issue_title"] == "New title"
        assert row["pr_number"] == 512


def test_delete_flow_removes_context_cache() -> None:
    """Hard deleting flow should also delete cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create cache
        store.upsert_flow_context_cache(
            branch="task/issue-329",
            task_issue_number=329,
            issue_title="old title",
            pr_number=100,
            pr_title="old pr",
        )

        # Hard delete flow (should delete cache too)
        store.delete_flow("task/issue-329", force=True)

        # Verify cache deleted
        cache = store.get_flow_context_cache("task/issue-329")
        assert cache is None, "Cache should be deleted when flow is hard deleted"


def test_get_nonexistent_cache_returns_none() -> None:
    """Getting cache for nonexistent branch should return None."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        cache = store.get_flow_context_cache("nonexistent/branch")
        assert cache is None
