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


def test_task_resume_has_no_remote_option() -> None:
    """`--remote` is not part of task resume."""
    result = runner.invoke(app, ["task", "resume", "303", "--remote"])

    assert result.exit_code != 0
    assert "No such option" in result.output


def test_task_resume_has_no_all_option() -> None:
    """`--all` is not part of task resume."""
    result = runner.invoke(app, ["task", "resume", "--all"])

    assert result.exit_code != 0
    assert "No such option" in result.output


@patch("vibe3.commands.task.FlowService")
@patch("vibe3.commands.task._build_resume_usecase")
@patch("vibe3.commands.task.resolve_command_branch")
def test_task_resume_branch_resolves_to_issue_number(
    resolve_branch: MagicMock,
    build_usecase: MagicMock,
    flow_service_cls: MagicMock,
) -> None:
    """`--branch task/issue-123` resolves to issue #123."""
    # Mock branch resolution
    resolve_branch.return_value = "task/issue-123"

    # Mock store.get_issue_links to return task issue
    flow_service = MagicMock()
    flow_service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 123}
    ]
    flow_service.list_flows.side_effect = [[_flow(123)], []]
    flow_service_cls.return_value = flow_service

    # Mock usecase
    usecase = MagicMock()
    usecase.resume_issues.return_value = {
        "requested": [123],
        "resumed": [{"number": 123, "resume_kind": "blocked"}],
        "skipped": [],
    }
    build_usecase.return_value = usecase

    result = runner.invoke(
        app, ["task", "resume", "--branch", "task/issue-123", "--yes"]
    )

    assert result.exit_code == 0
    call = usecase.resume_issues.call_args.kwargs
    assert call["issue_numbers"] == [123]


@patch("vibe3.commands.task.FlowService")
@patch("vibe3.commands.task._build_resume_usecase")
@patch("vibe3.commands.task.resolve_command_branch")
def test_task_resume_pr_resolves_to_issue_number(
    resolve_branch: MagicMock,
    build_usecase: MagicMock,
    flow_service_cls: MagicMock,
) -> None:
    """`--pr 456` resolves PR to branch, then to issue."""
    # Mock branch resolution from PR
    resolve_branch.return_value = "task/issue-456"

    # Mock store.get_issue_links to return task issue
    flow_service = MagicMock()
    flow_service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]
    flow_service.list_flows.side_effect = [[_flow(456)], []]
    flow_service_cls.return_value = flow_service

    # Mock usecase
    usecase = MagicMock()
    usecase.resume_issues.return_value = {
        "requested": [456],
        "resumed": [{"number": 456, "resume_kind": "blocked"}],
        "skipped": [],
    }
    build_usecase.return_value = usecase

    result = runner.invoke(app, ["task", "resume", "--pr", "456", "--yes"])

    assert result.exit_code == 0
    call = usecase.resume_issues.call_args.kwargs
    assert call["issue_numbers"] == [456]


def test_task_resume_branch_and_position_conflict() -> None:
    """`--branch 123 456` should error (conflict)."""
    result = runner.invoke(app, ["task", "resume", "--branch", "task/issue-123", "456"])

    assert result.exit_code != 0
    assert "Cannot combine --branch/--pr with positional issue numbers" in result.output


def test_task_resume_blocked_and_branch_conflict() -> None:
    """`--blocked --branch 123` should error."""
    result = runner.invoke(
        app, ["task", "resume", "--blocked", "--branch", "task/issue-123"]
    )

    assert result.exit_code != 0
    assert "Cannot combine --blocked with --branch or --pr" in result.output
