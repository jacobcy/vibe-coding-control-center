"""Tests for task resume command semantics."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestration import IssueState

runner = CliRunner()


def _flow(issue_number: int = 303) -> FlowStatusResponse:
    return FlowStatusResponse(
        branch=f"task/issue-{issue_number}",
        flow_slug=f"issue-{issue_number}",
        flow_status="active",
        latest_actor="test",
        task_issue_number=issue_number,
    )


@patch("vibe3.commands.task.FlowService")
@patch("vibe3.commands.task._build_resume_usecase")
def test_task_resume_issue_defaults_to_label_auto(
    build_usecase: MagicMock,
    flow_service_cls: MagicMock,
) -> None:
    """`vibe3 task resume 303` is equivalent to `--label auto`."""
    usecase = MagicMock()
    usecase.resume_issues.return_value = {
        "requested": [303],
        "resumed": [{"number": 303, "resume_kind": "blocked"}],
        "skipped": [],
    }
    build_usecase.return_value = usecase

    flow_service = MagicMock()
    flow_service.list_flows.side_effect = [[_flow(303)], []]
    flow_service_cls.return_value = flow_service

    result = runner.invoke(app, ["task", "resume", "303", "--yes"])

    assert result.exit_code == 0
    call = usecase.resume_issues.call_args.kwargs
    assert call["issue_numbers"] == [303]
    assert call["label_state"] == ""
    assert call["remote"] is False


@patch("vibe3.commands.task.FlowService")
@patch("vibe3.commands.task._build_resume_usecase")
def test_task_resume_blocked_defaults_to_label_auto(
    build_usecase: MagicMock,
    flow_service_cls: MagicMock,
) -> None:
    """`vibe3 task resume --blocked` also defaults to label auto."""
    usecase = MagicMock()
    usecase.status_service.fetch_orchestrated_issues.return_value = [
        {"number": 303, "state": IssueState.BLOCKED}
    ]
    usecase.resume_issues.return_value = {
        "requested": [303],
        "resumed": [{"number": 303, "resume_kind": "blocked"}],
        "skipped": [],
    }
    build_usecase.return_value = usecase

    flow_service = MagicMock()
    flow_service.list_flows.side_effect = [[_flow(303)], []]
    flow_service_cls.return_value = flow_service

    result = runner.invoke(app, ["task", "resume", "--blocked", "--yes"])

    assert result.exit_code == 0
    call = usecase.resume_issues.call_args.kwargs
    assert call["label_state"] == ""


@patch("vibe3.commands.task.FlowService")
@patch("vibe3.commands.task._build_resume_usecase")
def test_task_resume_label_ready_preserves_explicit_label(
    build_usecase: MagicMock,
    flow_service_cls: MagicMock,
) -> None:
    """Explicit labels still override auto inference."""
    usecase = MagicMock()
    usecase.resume_issues.return_value = {
        "requested": [303],
        "resumed": [{"number": 303, "resume_kind": "blocked"}],
        "skipped": [],
    }
    build_usecase.return_value = usecase

    flow_service = MagicMock()
    flow_service.list_flows.side_effect = [[_flow(303)], []]
    flow_service_cls.return_value = flow_service

    result = runner.invoke(app, ["task", "resume", "303", "--label", "ready", "--yes"])

    assert result.exit_code == 0
    call = usecase.resume_issues.call_args.kwargs
    assert call["label_state"] == "ready"


def test_task_resume_rejects_remote_without_rebuild() -> None:
    """`--remote` is destructive-rebuild-only and no longer valid on task resume."""
    result = runner.invoke(app, ["task", "resume", "303", "--remote"])

    assert result.exit_code != 0
    assert "--remote is only valid for vibe3 flow rebuild" in result.output
