"""Tests for TaskResumeResolver service."""

import tempfile
from pathlib import Path

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.data_source import DataSource


def test_resolve_local_reads_from_sqlite():
    """Test local source reads from SQLite."""
    from vibe3.services.flow_service import FlowService
    from vibe3.services.task_resume_resolver import TaskResumeResolver

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        # Create flow in SQLite with issue link
        store.update_flow_state(
            "task/issue-123",
            flow_slug="issue-123",
            flow_status="blocked",
            blocked_by_issue=456,
            blocked_reason="Waiting for dependency",
        )

        # Link issue to flow
        store.add_issue_link(
            branch="task/issue-123",
            issue_number=123,
            role="task",
        )

        flow_service = FlowService(store=store)
        resolver = TaskResumeResolver(store=store, flow_service=flow_service)

        result = resolver.resolve_resume_state(
            issue_number=123,
            source="local",
        )

        # Verify result comes from local SQLite
        assert result is not None
        assert result.data_source == DataSource.LOCAL_SQLITE
        assert result.issue_number == 123
        assert result.branch == "task/issue-123"
        assert result.blocked_by_issue == 456
        assert result.blocked_reason == "Waiting for dependency"
