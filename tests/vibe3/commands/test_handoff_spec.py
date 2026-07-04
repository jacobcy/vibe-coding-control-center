"""Contract tests for `vibe3 handoff spec` command (US1, FR-005).

Mirrors the `handoff plan` command contract (see test_handoff_advanced_commands).
The command must delegate to ``HandoffService.record_spec`` — the single
canonical write path established in Phase 2 (T011/T012).
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.exceptions import UserError

runner = CliRunner()


@patch("vibe3.commands.handoff_write.HandoffService")
@patch("vibe3.services.FlowService")
def test_handoff_spec_command_delegates_to_record_spec(
    mock_flow_service_class, mock_service_class
) -> None:
    """`handoff spec <canonical>` routes to HandoffService.record_spec."""
    mock_flow_service = MagicMock()
    mock_flow_service.get_current_branch.return_value = "task/test-branch"
    mock_flow_service_class.return_value = mock_flow_service

    mock_service = MagicMock()
    mock_service_class.return_value = mock_service

    result = runner.invoke(
        app,
        [
            "handoff",
            "spec",
            ".specify/specs/012-foo/spec.md",
            "--actor",
            "planner/claude",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Spec handoff recorded" in result.output
    mock_service.record_spec.assert_called_once_with(
        ".specify/specs/012-foo/spec.md",
        "planner/claude",
        branch="task/test-branch",
    )


@patch("vibe3.commands.handoff_write.HandoffService")
@patch("vibe3.services.FlowService")
def test_handoff_spec_command_propagates_validation_error(
    mock_flow_service_class, mock_service_class
) -> None:
    """Invalid spec_ref surfaces as non-zero exit (G1 write-strict contract)."""
    mock_flow_service = MagicMock()
    mock_flow_service.get_current_branch.return_value = "task/test-branch"
    mock_flow_service_class.return_value = mock_flow_service

    mock_service = MagicMock()
    mock_service.record_spec.side_effect = UserError(
        "spec_ref must be a canonical repository-relative path matching "
        ".specify/specs/<NNN-slug>/spec.md"
    )
    mock_service_class.return_value = mock_service

    result = runner.invoke(
        app,
        ["handoff", "spec", "#3310", "--actor", "planner/claude"],
    )

    assert result.exit_code != 0
    mock_service.record_spec.assert_called_once()
