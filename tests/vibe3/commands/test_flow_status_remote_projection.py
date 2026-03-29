"""Tests for flow status remote-first PR projection behavior."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.commands.flow_status import _fetch_issue_titles
from vibe3.models.flow import FlowState, FlowStatusResponse
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


def test_fetch_issue_titles_resolves_pr_by_branch_when_local_cache_missing() -> None:
    gh = MagicMock()
    gh.get_pr.return_value = _mock_pr()
    flow_status = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        pr_number=None,
    )

    _titles, pr_data, network_error, _milestone = _fetch_issue_titles(gh, flow_status)

    assert network_error is False
    assert pr_data is not None
    assert pr_data["number"] == 123
    gh.get_pr.assert_called_once_with(branch="task/demo")


def test_fetch_issue_titles_falls_back_to_branch_when_cached_pr_not_found() -> None:
    gh = MagicMock()
    gh.get_pr.side_effect = [None, _mock_pr(number=456)]
    flow_status = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        pr_number=999,
    )

    _titles, pr_data, network_error, _milestone = _fetch_issue_titles(gh, flow_status)

    assert network_error is False
    assert pr_data is not None
    assert pr_data["number"] == 456
    assert gh.get_pr.call_count == 2
    assert gh.get_pr.call_args_list[0].args == (999,)
    assert gh.get_pr.call_args_list[1].kwargs == {"branch": "task/demo"}


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
