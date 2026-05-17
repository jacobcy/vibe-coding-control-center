"""Tests for the handoff next command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def test_handoff_next_sets_next_step_for_numeric_branch() -> None:
    service = MagicMock()

    # Mock store with flow binding
    mock_store = MagicMock()
    mock_store.get_flows_by_issue.return_value = [
        {"branch": "task/issue-235", "flow_status": "active"}
    ]
    service.store = mock_store

    # Mock FlowService in both locations (handoff_write uses resolve_branch_arg)
    mock_flow_service = MagicMock()
    mock_flow_service.store = mock_store

    with (
        patch("vibe3.commands.handoff_write.HandoffService", return_value=service),
        patch("vibe3.utils.branch_arg.FlowService", return_value=mock_flow_service),
    ):
        result = runner.invoke(
            app,
            [
                "handoff",
                "next",
                "Finalize PR",
                "--branch",
                "235",
                "--actor",
                "test-actor",
            ],
        )

    assert result.exit_code == 0
    service.record_next_step.assert_called_once_with(
        "task/issue-235",
        "Finalize PR",
        "test-actor",
    )


def test_handoff_next_rejects_nonexistent_flow() -> None:
    """Should fail-fast with UserError if no flow found."""
    service = MagicMock()

    # Mock store with no flow binding and no unbound candidates
    mock_store = MagicMock()
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = None  # No unbound candidates either
    service.store = mock_store

    # Mock FlowService in branch_arg (resolver creates its own instance)
    mock_flow_service = MagicMock()
    mock_flow_service.store = mock_store

    with (
        patch("vibe3.commands.handoff_write.HandoffService", return_value=service),
        patch("vibe3.utils.branch_arg.FlowService", return_value=mock_flow_service),
    ):
        result = runner.invoke(
            app,
            ["handoff", "next", "message", "--branch", "999"],
        )

    assert result.exit_code == 1
    # UserError should be captured in the exception attribute
    assert result.exception is not None
    assert "No flow found for issue #999" in str(result.exception)
    # Should NOT call record_next_step when flow doesn't exist
    service.record_next_step.assert_not_called()
