"""Tests for flow show auto-ensure behavior."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowState

runner = CliRunner()


@patch("vibe3.commands.flow.render_flow_timeline")
@patch("vibe3.commands.flow.FlowService")
def test_flow_show_auto_ensures_current_branch(flow_service_cls, _render_timeline) -> None:
    """flow show should auto-ensure flow for current branch before showing timeline."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/auto-ensure-show"
    flow_service.get_flow_timeline.return_value = {
        "state": FlowState(
            branch="task/auto-ensure-show",
            flow_slug="auto_ensure_show",
            flow_status="active",
        ),
        "events": [],
    }
    flow_service_cls.return_value = flow_service

    result = runner.invoke(app, ["flow", "show"])

    assert result.exit_code == 0
    flow_service.ensure_flow_for_branch.assert_called_once_with("task/auto-ensure-show")
