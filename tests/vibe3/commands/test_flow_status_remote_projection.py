"""Tests for flow status remote-first PR projection behavior."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowState
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
    """PR data is fetched by branch via projection service, not cached pr_number."""
    mock_pr_service = MagicMock()
    mock_pr_service.get_pr.return_value = _mock_pr()
    mock_flow_service = MagicMock()

    from vibe3.models.flow import FlowStatusResponse

    mock_flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        pr_number=None,
    )

    from vibe3.services.flow_projection_service import FlowProjectionService

    svc = FlowProjectionService(
        flow_service=mock_flow_service, pr_service=mock_pr_service
    )
    projection = svc.get_projection("task/demo")

    assert projection.pr_number == 123
    assert projection.pr_title == "Demo PR"
    mock_pr_service.get_pr.assert_called_once_with(branch="task/demo")


def test_projection_pr_branch_fallback_when_cached_misses() -> None:
    """When PR is not found by cached number, projection falls back to branch."""
    mock_pr_service = MagicMock()
    mock_pr_service.get_pr.return_value = _mock_pr(number=456)
    mock_flow_service = MagicMock()

    from vibe3.models.flow import FlowStatusResponse

    mock_flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        pr_number=999,
    )

    from vibe3.services.flow_projection_service import FlowProjectionService

    svc = FlowProjectionService(
        flow_service=mock_flow_service, pr_service=mock_pr_service
    )
    projection = svc.get_projection("task/demo")

    # PR fetched by branch, not by cached pr_number
    assert projection.pr_number == 456
    mock_pr_service.get_pr.assert_called_once_with(branch="task/demo")


def _make_flow_state(
    branch: str = "task/demo",
    status: str = "active",
    pr_number: int | None = None,
) -> FlowState:
    return FlowState(
        branch=branch,
        flow_slug=branch.replace("/", "-"),
        flow_status=status,
        pr_number=pr_number,
        updated_at="2026-03-29T00:00:00",
    )


@patch("vibe3.commands.flow_status.FlowService")
def test_flow_status_default_filters_active(mock_service_class) -> None:
    """flow status without --all only shows active flows."""
    mock_service = MagicMock()
    mock_service.list_flows.return_value = [
        _make_flow_state("task/active-1"),
        _make_flow_state("task/active-2"),
    ]
    mock_service_class.return_value = mock_service

    result = runner.invoke(app, ["flow", "status"])

    assert result.exit_code == 0
    mock_service.list_flows.assert_called_once_with(status="active")


@patch("vibe3.commands.flow_status.FlowService")
def test_flow_status_all_shows_everything(mock_service_class) -> None:
    """flow status --all passes status=None to list_flows."""
    mock_service = MagicMock()
    mock_service.list_flows.return_value = [
        _make_flow_state("task/active-1"),
        _make_flow_state("task/old-done", status="done"),
        _make_flow_state("task/aborted-1", status="aborted"),
    ]
    mock_service_class.return_value = mock_service

    result = runner.invoke(app, ["flow", "status", "--all"])

    assert result.exit_code == 0
    mock_service.list_flows.assert_called_once_with(status=None)
