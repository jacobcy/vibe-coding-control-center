"""Tests for FlowStatusResolver service."""

from unittest.mock import Mock

import pytest

from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import UserError
from vibe3.models.data_source import DataSource
from vibe3.models.flow import FlowStatusResponse
from vibe3.services.flow_service import FlowService
from vibe3.services.flow_status_resolver import FlowStatusResolver


class TestFlowStatusResolver:
    """Test suite for FlowStatusResolver."""

    def test_resolver_local_reads_from_sqlite(self) -> None:
        """Test local strategy reads from SQLite and sets data_source."""
        # Setup
        mock_flow_service = Mock(spec=FlowService)
        mock_response = FlowStatusResponse(
            branch="test-branch",
            flow_slug="test-flow",
            flow_status="active",
        )
        mock_flow_service.get_flow_status.return_value = mock_response

        resolver = FlowStatusResolver(flow_service=mock_flow_service)

        # Execute
        result = resolver.resolve(
            branch="test-branch",
            source="local",
            issue_number=None,
        )

        # Verify
        assert result.branch == "test-branch"
        assert result.flow_slug == "test-flow"
        assert result.flow_status == "active"
        assert result.data_source == DataSource.LOCAL_SQLITE
        mock_flow_service.get_flow_status.assert_called_once_with("test-branch")

    def test_resolver_local_raises_if_flow_missing(self) -> None:
        """Test local strategy raises UserError if flow not found."""
        # Setup
        mock_flow_service = Mock(spec=FlowService)
        mock_flow_service.get_flow_status.return_value = None

        resolver = FlowStatusResolver(flow_service=mock_flow_service)

        # Execute & Verify
        with pytest.raises(UserError, match="Flow not found for branch"):
            resolver.resolve(
                branch="missing-branch",
                source="local",
                issue_number=None,
            )

    def test_resolver_remote_reads_from_issue_body(self) -> None:
        """Test remote strategy reads from GitHub issue body."""
        # Setup
        mock_github_client = Mock(spec=GitHubClient)
        issue_body = """
Some issue content

<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #123
- **Blocked reason**: Waiting for dependency

<!-- vibe3-flow-state-end -->
"""
        mock_github_client.get_issue_body.return_value = issue_body

        resolver = FlowStatusResolver(github_client=mock_github_client)

        # Execute
        result = resolver.resolve(
            branch="test-branch",
            source="remote",
            issue_number=456,
        )

        # Verify
        assert result.branch == "test-branch"
        assert (
            result.flow_status == "active"
        )  # "blocked" mapped to "active" (inferred from blocked_by_issue)
        assert result.blocked_by_issue == 123
        assert result.blocked_reason == "Waiting for dependency"
        assert result.data_source == DataSource.ISSUE_BODY_FALLBACK
        mock_github_client.get_issue_body.assert_called_once_with(456)

    def test_resolver_remote_requires_issue_number(self) -> None:
        """Test remote strategy raises ValueError if issue_number missing."""
        # Setup
        resolver = FlowStatusResolver()

        # Execute & Verify
        with pytest.raises(ValueError, match="issue_number required for remote source"):
            resolver.resolve(
                branch="test-branch",
                source="remote",
                issue_number=None,
            )

    def test_resolver_auto_fallback_to_issue_body(self) -> None:
        """Test auto strategy falls back to issue body when local fails."""
        # Setup
        mock_flow_service = Mock(spec=FlowService)
        mock_flow_service.get_flow_status.return_value = None  # Local fails

        mock_github_client = Mock(spec=GitHubClient)
        issue_body = """
<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: active

<!-- vibe3-flow-state-end -->
"""
        mock_github_client.get_issue_body.return_value = issue_body

        resolver = FlowStatusResolver(
            flow_service=mock_flow_service,
            github_client=mock_github_client,
        )

        # Execute
        result = resolver.resolve(
            branch="test-branch",
            source="auto",
            issue_number=789,
        )

        # Verify
        assert result.branch == "test-branch"
        assert result.flow_status == "active"
        assert result.data_source == DataSource.ISSUE_BODY_FALLBACK
        mock_flow_service.get_flow_status.assert_called_once_with("test-branch")
        mock_github_client.get_issue_body.assert_called_once_with(789)

    def test_resolver_auto_raises_if_no_issue_number_for_fallback(self) -> None:
        """Test auto raises ValueError if no issue_number for fallback."""
        # Setup
        mock_flow_service = Mock(spec=FlowService)
        mock_flow_service.get_flow_status.return_value = None  # Local fails

        resolver = FlowStatusResolver(flow_service=mock_flow_service)

        # Execute & Verify
        with pytest.raises(ValueError, match="issue_number required for auto fallback"):
            resolver.resolve(
                branch="test-branch",
                source="auto",
                issue_number=None,
            )

    def test_resolver_auto_uses_local_when_available(self) -> None:
        """Test auto strategy uses local when available."""
        # Setup
        mock_flow_service = Mock(spec=FlowService)
        mock_response = FlowStatusResponse(
            branch="test-branch",
            flow_slug="test-flow",
            flow_status="active",
        )
        mock_flow_service.get_flow_status.return_value = mock_response

        mock_github_client = Mock(spec=GitHubClient)

        resolver = FlowStatusResolver(
            flow_service=mock_flow_service,
            github_client=mock_github_client,
        )

        # Execute
        result = resolver.resolve(
            branch="test-branch",
            source="auto",
            issue_number=789,
        )

        # Verify
        assert result.branch == "test-branch"
        assert result.flow_status == "active"
        assert result.data_source == DataSource.LOCAL_SQLITE
        mock_flow_service.get_flow_status.assert_called_once_with("test-branch")
        mock_github_client.get_issue_body.assert_not_called()

    def test_resolver_remote_empty_projection_returns_default(self) -> None:
        """Test remote strategy with empty/missing projection returns defaults."""
        # Setup
        mock_github_client = Mock(spec=GitHubClient)
        mock_github_client.get_issue_body.return_value = "No managed section here"

        resolver = FlowStatusResolver(github_client=mock_github_client)

        # Execute
        result = resolver.resolve(
            branch="test-branch",
            source="remote",
            issue_number=123,
        )

        # Verify
        assert result.branch == "test-branch"
        assert result.flow_status == "active"
        assert result.data_source == DataSource.ISSUE_BODY_FALLBACK
