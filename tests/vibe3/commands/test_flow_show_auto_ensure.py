"""Tests for flow show auto-ensure behavior."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowState

runner = CliRunner()


@patch("vibe3.commands.flow.render_flow_timeline")
@patch("vibe3.commands.flow.ensure_flow_for_current_branch")
def test_flow_show_auto_ensures_current_branch(mock_ensure, _render_timeline) -> None:
    """flow show should auto-ensure flow for current branch before showing timeline."""
    flow_service = MagicMock()
    flow_service.get_flow_timeline.return_value = {
        "state": FlowState(
            branch="task/auto-ensure-show",
            flow_slug="auto_ensure_show",
            flow_status="active",
        ),
        "events": [],
    }
    mock_ensure.return_value = (flow_service, "task/auto-ensure-show")

    result = runner.invoke(app, ["flow", "show"])

    assert result.exit_code == 0
    mock_ensure.assert_called_once()
