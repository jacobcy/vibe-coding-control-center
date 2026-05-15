"""Tests for the handoff next command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def test_handoff_next_sets_next_step_for_numeric_branch() -> None:
    service = MagicMock()

    with patch("vibe3.commands.handoff_write.HandoffService", return_value=service):
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
    """Should reject if target branch has no flow."""
    service = MagicMock()
    # Mock get_flow_state to return None (flow doesn't exist)
    service.store.get_flow_state.return_value = None

    with patch("vibe3.commands.handoff_write.HandoffService", return_value=service):
        result = runner.invoke(
            app,
            ["handoff", "next", "message", "--branch", "999"],
        )

    assert result.exit_code == 1
    assert "没有 flow" in result.output
    # Should NOT call record_next_step when flow doesn't exist
    service.record_next_step.assert_not_called()
