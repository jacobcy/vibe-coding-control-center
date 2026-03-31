"""Tests for flow show policy (no auto-ensure)."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse

runner = CliRunner()


@patch("vibe3.commands.flow_status.render_flow_timeline")
@patch("vibe3.commands.flow_status.FlowService")
def test_flow_show_hint_when_not_registered(mock_service_cls, _render_timeline) -> None:
    """flow show should NOT auto-ensure flow; it should show a hint instead."""
    mock_service = MagicMock()
    mock_service.get_current_branch.return_value = "feature/unregistered"
    mock_service.get_flow_status.return_value = None
    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["flow", "show"])

    assert result.exit_code == 0
    assert "尚未注册为 flow" in result.output
    mock_service.get_flow_timeline.assert_not_called()


@patch("vibe3.commands.flow_status.render_flow_timeline")
@patch("vibe3.commands.flow_status.FlowService")
def test_flow_show_timeline_when_registered(mock_service_cls, _render_timeline) -> None:
    """flow show should show timeline if flow is already registered."""
    mock_service = MagicMock()
    branch = "feature/registered"
    mock_service.get_current_branch.return_value = branch

    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug="registered",
        flow_status="active",
    )
    mock_service.get_flow_status.return_value = flow_status
    mock_service.get_flow_timeline.return_value = {
        "state": flow_status,
        "events": [],
    }
    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["flow", "show"])

    assert result.exit_code == 0
    mock_service.get_flow_timeline.assert_called_once_with(branch)
