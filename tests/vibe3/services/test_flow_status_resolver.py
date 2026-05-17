"""Tests for FlowStatusResolver source-aware reads."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.data_source import DataSource
from vibe3.services.flow_status_resolver import FlowStatusResolver


def test_resolver_local_reads_from_sqlite():
    """SourceOption 'local' reads from SQLite only, no fallback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        resolver = FlowStatusResolver(store=store)

        # Create flow in SQLite
        store.update_flow_state(
            "dev/issue-123",
            flow_slug="issue-123",
            flow_status="active",
        )

        result = resolver.resolve(
            branch="dev/issue-123",
            source="local",
        )

        assert result.branch == "dev/issue-123"
        assert result.flow_slug == "issue-123"
        assert result.flow_status == "active"
        assert result.data_source == DataSource.LOCAL_SQLITE


def test_resolver_auto_fallback_to_issue_body():
    """SourceOption 'auto' falls back to issue body projection when SQLite missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteClient(db_path=str(db_path))

        resolver = FlowStatusResolver(store=store)

        # No flow in SQLite (deleted or remote machine)
        with patch(
            "vibe3.clients.github_client.GitHubClient"
        ) as mock_github_client_class:
            mock_github_client = MagicMock()
            mock_github_client_class.return_value = mock_github_client

            mock_github_client.get_issue_body.return_value = """
<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456
- **Blocked reason**: Waiting for dependency

<!-- vibe3-flow-state-end -->
"""

            result = resolver.resolve(
                branch="dev/issue-123",
                source="auto",
                issue_number=123,  # Required for fallback
            )

            assert result.branch == "dev/issue-123"
            assert result.flow_slug == "dev-issue-123"
            # Note: "blocked" is migrated to "active" by FlowStatusResponse validator
            assert result.flow_status == "active"
            assert result.blocked_by_issue == 456
            assert result.blocked_reason == "Waiting for dependency"
            assert result.data_source == DataSource.ISSUE_BODY_FALLBACK
            mock_github_client.get_issue_body.assert_called_once_with(123)
