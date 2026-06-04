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
    mock_store = MagicMock()
    mock_store.get_task_issue_number.return_value = None
    mock_service.store = mock_store
    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["flow", "show"])

    assert result.exit_code == 0
    assert "尚未注册为 flow" in result.output
    mock_service.get_flow_timeline.assert_not_called()


@patch("vibe3.commands.flow_status.render_flow_timeline")
@patch("vibe3.services.flow_status_resolver.FlowStatusResolver")
@patch("vibe3.commands.flow_status.find_parent_branch", return_value=None)
@patch("vibe3.commands.flow_status.FlowService")
def test_flow_show_timeline_when_registered(
    mock_service_cls, _find_parent_branch, mock_resolver_cls, _render_timeline
) -> None:
    """flow show should show timeline if flow is already registered."""
    mock_service = MagicMock()
    branch = "feature/registered"
    mock_service.get_current_branch.return_value = branch

    flow_status = FlowStatusResponse(
        branch=branch,
        flow_slug="registered",
        flow_status="active",
    )

    # Mock resolver to return flow_status
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = flow_status
    mock_resolver_cls.return_value = mock_resolver

    # Mock store to return empty events
    mock_store = MagicMock()
    mock_store.get_events.return_value = []
    mock_store.get_task_issue_number.return_value = None
    mock_service.store = mock_store

    # Mock get_flow_status (resolver uses it internally)
    mock_service.get_flow_status.return_value = flow_status
    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["flow", "show"])

    assert result.exit_code == 0
    # Should NOT call get_flow_timeline anymore (uses resolver + store.get_events)
    mock_service.get_flow_timeline.assert_not_called()
    # Should call resolver.resolve with correct branch
    mock_resolver.resolve.assert_called_once_with(
        branch=branch,
        remote=False,
        issue_number=None,
    )
    # Should call store.get_events to get timeline events
    mock_store.get_events.assert_called_once_with(branch, limit=100)


@patch("vibe3.commands.flow_status.render_flow_timeline")
@patch("vibe3.services.flow_status_resolver.FlowStatusResolver")
@patch("vibe3.commands.flow_status.find_parent_branch", return_value=None)
@patch("vibe3.commands.flow_status.FlowService")
def test_flow_show_numeric_issue_resolves_branch(
    mock_service_cls, _find_parent_branch, mock_resolver_cls, _render_timeline
) -> None:
    """flow show 436 should resolve to task/dev issue branch."""
    mock_service = MagicMock()

    flow_status = FlowStatusResponse(
        branch="task/issue-436",
        flow_slug="issue-436",
        flow_status="active",
    )

    # Mock store with both get_flows_by_issue and get_events
    mock_store = MagicMock()
    mock_store.get_flows_by_issue.return_value = [
        {"branch": "task/issue-436", "flow_status": "active"}
    ]
    mock_store.get_events.return_value = []
    mock_store.get_task_issue_number.return_value = 436
    mock_service.store = mock_store

    def get_flow_status(branch: str):
        if branch == "task/issue-436":
            return flow_status
        return None

    mock_service.get_flow_status.side_effect = get_flow_status

    # Mock resolver to return flow_status
    mock_resolver = MagicMock()
    mock_resolver.resolve.return_value = flow_status
    mock_resolver_cls.return_value = mock_resolver

    mock_service_cls.return_value = mock_service

    result = runner.invoke(app, ["flow", "show", "436"])

    assert (
        result.exit_code == 0
    ), f"Exit code: {result.exit_code}, Output: {result.output}"
    # Should NOT call get_flow_timeline anymore (uses resolver + store.get_events)
    mock_service.get_flow_timeline.assert_not_called()
    # Should call resolver.resolve with resolved branch and parsed issue_number
    mock_resolver.resolve.assert_called_once_with(
        branch="task/issue-436",
        remote=False,
        issue_number=436,  # parsed from input "436"
    )
