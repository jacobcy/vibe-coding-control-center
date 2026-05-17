"""Tests for flow show --source parameter."""

from unittest.mock import MagicMock, patch

from vibe3.commands.flow_status import show
from vibe3.models.data_source import DataSource


def test_flow_show_source_local():
    """flow show --source local uses resolver with local strategy."""
    with patch(
        "vibe3.services.flow_status_resolver.FlowStatusResolver.resolve"
    ) as mock_resolve:
        mock_resolve.return_value = MagicMock(
            branch="dev/issue-123",
            flow_slug="issue-123",
            flow_status="active",
            data_source=DataSource.LOCAL_SQLITE,
        )

        with patch("vibe3.commands.flow_status.FlowService"):
            with patch(
                "vibe3.commands.flow_status.resolve_issue_branch_input"
            ) as mock_resolve_branch:
                mock_resolve_branch.return_value = "dev/issue-123"

                # Simulate CLI call: flow show --source local
                show(branch="dev/issue-123", source="local", output_format="json")

                mock_resolve.assert_called_once()
                call_kwargs = mock_resolve.call_args[1]
                assert call_kwargs["source"] == "local"


def test_flow_show_source_auto_fallback():
    """flow show --source auto falls back to issue body when SQLite missing."""
    with patch(
        "vibe3.services.flow_status_resolver.FlowStatusResolver.resolve"
    ) as mock_resolve:
        mock_resolve.return_value = MagicMock(
            branch="dev/issue-123",
            flow_slug="dev-issue-123",
            flow_status="active",
            blocked_reason="Waiting for #456",
            data_source=DataSource.ISSUE_BODY_FALLBACK,
        )

        with patch("vibe3.commands.flow_status.FlowService"):
            with patch(
                "vibe3.commands.flow_status.resolve_issue_branch_input"
            ) as mock_resolve_branch:
                mock_resolve_branch.return_value = "dev/issue-123"

                # Simulate CLI call: flow show --source auto
                show(branch="dev/issue-123", source="auto", output_format="json")

                mock_resolve.assert_called_once()
                call_kwargs = mock_resolve.call_args[1]
                assert call_kwargs["source"] == "auto"
