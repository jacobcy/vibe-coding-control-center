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
