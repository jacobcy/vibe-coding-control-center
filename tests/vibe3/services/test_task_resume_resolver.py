"""Tests for TaskResumeResolver service."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_resolve_remote_reads_from_github_api():
    """Test remote source reads from GitHub API."""
    from vibe3.services.task_resume_resolver import TaskResumeResolver

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        resolver = TaskResumeResolver(store=store)

        with patch.object(
            resolver,
            "_read_remote",
            return_value=MagicMock(
                issue_number=123,
                branch="task/issue-123",
                blocked_by_issue=789,
                blocked_reason="Need approval",
                assignee="testuser",
                labels=["blocked"],
                data_source=DataSource.GITHUB_API,
            ),
        ):
            result = resolver.resolve_resume_state(
                issue_number=123,
                source="remote",
                repo="owner/repo",
            )

        # Verify result comes from GitHub API
        assert result is not None
        assert result.data_source == DataSource.GITHUB_API
        assert result.issue_number == 123
        assert result.blocked_by_issue == 789
        assert result.blocked_reason == "Need approval"
        assert result.assignee == "testuser"
        assert result.labels == ["blocked"]


def test_resolve_auto_fallback_to_remote():
    """Test auto source falls back to remote when local fails."""
    from vibe3.exceptions import UserError
    from vibe3.services.task_resume_resolver import TaskResumeResolver

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        resolver = TaskResumeResolver(store=store)

        # Mock _read_local to raise UserError
        with patch.object(
            resolver, "_read_local", side_effect=UserError("No flow found")
        ):
            # Mock _read_remote to return success
            with patch.object(
                resolver,
                "_read_remote",
                return_value=MagicMock(
                    issue_number=123,
                    branch="task/issue-123",
                    data_source=DataSource.GITHUB_API,
                ),
            ):
                result = resolver.resolve_resume_state(
                    issue_number=123,
                    source="auto",
                    repo="owner/repo",
                )

        # Verify fallback to remote
        assert result is not None
        assert result.data_source == DataSource.GITHUB_API
