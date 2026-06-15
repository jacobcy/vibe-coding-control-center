"""Tests for flow restore command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.flow import app as flow_app

runner = CliRunner()


@patch("vibe3.services.shared.branches.resolve_branch_arg")
@patch("vibe3.clients.SQLiteClient")
def test_restore_aborted_flow_without_tombstone(
    mock_client_class, mock_resolve_branch
) -> None:
    """Test that restore command succeeds for aborted flow with deleted_at=NULL.

    This tests the deadlock scenario where:
    - flow_status='aborted' (set by abort_flow)
    - deleted_at is NULL (no tombstone created)

    The restore command should succeed and call restore_flow method.
    """
    # Setup mocks
    mock_resolve_branch.return_value = "task/issue-789"
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    # Mock flow in deadlock state: aborted but no tombstone
    mock_flow = {
        "branch": "task/issue-789",
        "flow_slug": "issue_789",
        "flow_status": "aborted",
        "deleted_at": None,  # No tombstone
    }
    mock_client.get_flow_state_include_deleted.return_value = mock_flow

    # Execute restore command
    result = runner.invoke(flow_app, ["restore", "task/issue-789"])

    # Should succeed
    assert result.exit_code == 0
    assert "restored successfully" in result.output

    # Verify restore_flow was called
    mock_client.restore_flow.assert_called_once_with("task/issue-789")


@patch("vibe3.services.shared.branches.resolve_branch_arg")
@patch("vibe3.clients.SQLiteClient")
def test_restore_soft_deleted_flow(mock_client_class, mock_resolve_branch) -> None:
    """Test that restore command succeeds for soft-deleted flow."""
    # Setup mocks
    mock_resolve_branch.return_value = "task/issue-123"
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    # Mock soft-deleted flow
    mock_flow = {
        "branch": "task/issue-123",
        "flow_slug": "issue_123",
        "flow_status": "aborted",
        "deleted_at": "2024-01-01 00:00:00",  # Tombstone exists
    }
    mock_client.get_flow_state_include_deleted.return_value = mock_flow

    # Execute restore command
    result = runner.invoke(flow_app, ["restore", "task/issue-123"])

    # Should succeed
    assert result.exit_code == 0
    assert "restored successfully" in result.output

    # Verify restore_flow was called
    mock_client.restore_flow.assert_called_once_with("task/issue-123")


@patch("vibe3.services.shared.branches.resolve_branch_arg")
@patch("vibe3.clients.SQLiteClient")
def test_restore_already_active_flow(mock_client_class, mock_resolve_branch) -> None:
    """Test that restore command rejects already active flow."""
    # Setup mocks
    mock_resolve_branch.return_value = "task/issue-456"
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    # Mock active flow
    mock_flow = {
        "branch": "task/issue-456",
        "flow_slug": "issue_456",
        "flow_status": "active",
        "deleted_at": None,
    }
    mock_client.get_flow_state_include_deleted.return_value = mock_flow

    # Execute restore command
    result = runner.invoke(flow_app, ["restore", "task/issue-456"])

    # Should exit gracefully (exit code 0, no error)
    assert result.exit_code == 0
    assert "already active" in result.output

    # Verify restore_flow was NOT called
    mock_client.restore_flow.assert_not_called()


@patch("vibe3.services.shared.branches.resolve_branch_arg")
@patch("vibe3.clients.SQLiteClient")
def test_restore_nonexistent_flow(mock_client_class, mock_resolve_branch) -> None:
    """Test that restore command fails for nonexistent flow."""
    # Setup mocks
    mock_resolve_branch.return_value = "task/issue-999"
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    # Mock flow not found
    mock_client.get_flow_state_include_deleted.return_value = None

    # Execute restore command
    result = runner.invoke(flow_app, ["restore", "task/issue-999"])

    # Should fail
    assert result.exit_code == 1
    assert "not found" in result.output

    # Verify restore_flow was NOT called
    mock_client.restore_flow.assert_not_called()
