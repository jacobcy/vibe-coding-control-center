"""Tests for flow status remote-first PR projection behavior."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.pr import PRResponse, PRState

runner = CliRunner()


def _mock_pr(number: int = 123, branch: str = "task/demo") -> PRResponse:
    return PRResponse(
        number=number,
        title="Demo PR",
        body="Body",
        state=PRState.OPEN,
        head_branch=branch,
        base_branch="main",
        url=f"https://example.com/pr/{number}",
        draft=False,
    )


def test_projection_pr_resolves_by_branch() -> None:
    """PR data is fetched by branch via projection service."""
    mock_pr_service = MagicMock()
    mock_pr_service.github_client.list_prs_for_branch.return_value = [_mock_pr()]
    mock_flow_service = MagicMock()

    from vibe3.models.flow import FlowStatusResponse

    mock_flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
    )

    from vibe3.services.flow_projection_service import FlowProjectionService

    svc = FlowProjectionService(
        flow_service=mock_flow_service, pr_service=mock_pr_service
    )
    projection = svc.get_projection("task/demo")

    assert projection.pr_number == 123
    assert projection.pr_status == "OPEN"
    mock_pr_service.github_client.list_prs_for_branch.assert_called_once_with(
        "task/demo"
    )


def _make_flow_state(
    branch: str = "task/demo",
    status: str = "active",
) -> FlowStatusResponse:
    return FlowStatusResponse(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status=status,
        updated_at="2026-03-29T00:00:00",
    )


@patch("vibe3.commands.flow_status.FlowService")
def test_flow_status_default_filters_active(mock_service_class) -> None:
    """flow status without --all only shows active flows."""
    mock_service = MagicMock()
    mock_service.list_flows.return_value = [
        _make_flow_state("task/active-1"),
        _make_flow_state("task/active-2"),
        _make_flow_state("task/done-1", status="done"),
    ]
    mock_service_class.return_value = mock_service

    result = runner.invoke(app, ["flow", "status"])

    assert result.exit_code == 0
    # Use status filter "active" by default
    mock_service.list_flows.assert_called_once_with(status="active")


@patch("vibe3.commands.flow_status.FlowService")
def test_flow_status_all_includes_terminal_states(mock_service_class) -> None:
    """flow status --all includes flows in terminal states (done, aborted)."""
    mock_service = MagicMock()
    mock_service_class.return_value = mock_service

    runner.invoke(app, ["flow", "status", "--all"])

    # Pass status=None to show all
    mock_service.list_flows.assert_called_once_with(status=None)
