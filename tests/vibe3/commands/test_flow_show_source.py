"""Tests for flow show --source parameter."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.exceptions import UserError
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


@patch("vibe3.commands.flow_status.FlowService")
def test_flow_show_source_remote_no_issue_returns_user_error(
    mock_service_cls,
) -> None:
    """flow show --source remote without issue number should return clean user error."""
    mock_service = MagicMock()
    mock_service.get_current_branch.return_value = "feature/no-issue"
    mock_service.store.get_issue_links.return_value = []  # No task issue linked
    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["flow", "show", "--source", "remote"])

    # Should exit with error, not traceback
    assert result.exit_code == 1
    # Should raise UserError
    assert isinstance(result.exception, UserError)
    # Should NOT show Python traceback in output
    assert "Traceback" not in result.output


@patch("vibe3.commands.flow_status.render_flow_timeline")
@patch("vibe3.commands.flow_status.find_parent_branch", return_value=None)
@patch("vibe3.services.issue_flow_service.IssueFlowService")
@patch("vibe3.clients.github_client.GitHubClient")
@patch("vibe3.commands.flow_status.FlowService")
def test_flow_show_source_auto_fallback_to_issue_body(
    mock_service_cls,
    mock_github_client_cls,
    mock_issue_flow_service_cls,
    _find_parent_branch,
    _render_timeline,
) -> None:
    """flow show --source auto should fallback to issue body when local missing."""
    mock_store = MagicMock()
    mock_service = MagicMock()
    branch = "dev/issue-123"
    mock_service.get_current_branch.return_value = branch
    mock_service.get_flow_status.return_value = None  # Local missing
    mock_service.store = mock_store
    mock_store.get_issue_links.return_value = []  # No local link
    mock_service_cls.return_value = mock_service

    # Mock IssueFlowService to return issue number from branch name
    mock_issue_flow_service = MagicMock()
    mock_issue_flow_service_cls.return_value = mock_issue_flow_service
    mock_issue_flow_service.parse_issue_number_any.return_value = 123

    # Mock GitHub client to return issue body
    mock_github_client = MagicMock()
    mock_github_client_cls.return_value = mock_github_client
    mock_github_client.get_issue_body.return_value = """
<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: active

<!-- vibe3-flow-state-end -->
"""

    # Mock timeline response (required for successful flow show)
    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug="issue-123",
        flow_status="active",
    )
    mock_service.get_flow_timeline.return_value = {
        "state": flow_status,
        "events": [],
    }

    result = runner.invoke(app, ["flow", "show", "--source", "auto"])

    # Should succeed (fallback worked)
    assert result.exit_code == 0
    # Should call GitHub API for fallback
    mock_github_client.get_issue_body.assert_called_once_with(123)


@patch("vibe3.commands.flow_status.render_flow_timeline")
@patch("vibe3.commands.flow_status.find_parent_branch", return_value=None)
@patch("vibe3.services.issue_flow_service.IssueFlowService")
@patch("vibe3.clients.github_client.GitHubClient")
@patch("vibe3.commands.flow_status.FlowService")
def test_flow_show_source_auto_uses_parse_issue_number_any_fallback(
    mock_service_cls,
    mock_github_client_cls,
    mock_issue_flow_service_cls,
    _find_parent_branch,
    _render_timeline,
) -> None:
    """flow show --source auto uses parse_issue_number_any when local DB missing."""
    mock_store = MagicMock()
    mock_service = MagicMock()
    branch = "dev/issue-456"  # Branch name contains issue number
    mock_service.get_current_branch.return_value = branch
    mock_service.get_flow_status.return_value = None  # Local missing
    mock_service.store = mock_store
    mock_store.get_issue_links.return_value = []  # No local link
    mock_service_cls.return_value = mock_service

    # Mock IssueFlowService to return issue number from branch name
    mock_issue_flow_service = MagicMock()
    mock_issue_flow_service_cls.return_value = mock_issue_flow_service
    mock_issue_flow_service.parse_issue_number_any.return_value = 456

    # Mock GitHub client to return issue body
    mock_github_client = MagicMock()
    mock_github_client_cls.return_value = mock_github_client
    mock_github_client.get_issue_body.return_value = """
<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: active

<!-- vibe3-flow-state-end -->
"""

    # Mock timeline response (required for successful flow show)
    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug="issue-456",
        flow_status="active",
    )
    mock_service.get_flow_timeline.return_value = {
        "state": flow_status,
        "events": [],
    }

    result = runner.invoke(app, ["flow", "show", "--source", "auto"])

    # Should succeed (fallback with parse_issue_number_any worked)
    assert result.exit_code == 0
    # Should call GitHub API with issue number from branch name
    mock_github_client.get_issue_body.assert_called_once_with(456)
