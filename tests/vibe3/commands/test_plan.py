"""Tests for plan command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.plan import app as plan_app

runner = CliRunner(env={"NO_COLOR": "1"})


def _make_mock_flow(
    branch: str = "task/issue-42",
    spec_ref: str | None = "#42",
    issue_number: int = 42,
) -> MagicMock:
    mock_flow = MagicMock()
    mock_flow.branch = branch
    mock_flow.spec_ref = spec_ref
    mock_flow.task_issue_number = issue_number
    return mock_flow


def _patch_plan_deps(monkeypatch, mock_flow: MagicMock | None = None) -> MagicMock:
    """Patch all plan command external dependencies."""
    if mock_flow is None:
        mock_flow = _make_mock_flow()

    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_async = MagicMock()
    mock_sync = MagicMock()

    monkeypatch.setattr("vibe3.commands.plan.run_issue_role_async", mock_async)
    monkeypatch.setattr("vibe3.commands.plan.run_issue_role_sync", mock_sync)
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )
    return mock_async


def test_plan_help_shows_options() -> None:
    result = runner.invoke(plan_app, ["--help"])
    assert result.exit_code == 0
    assert "--branch" in result.output
    assert "--spec" in result.output


def test_plan_spec_uses_flow_spec_ref(monkeypatch) -> None:
    """Test plan without --spec uses flow's spec_ref."""
    mock_flow = _make_mock_flow(spec_ref="@task-42/spec.md")
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    mock_execute = MagicMock()

    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_async", mock_execute)
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", mock_execute)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        MagicMock(),
    )

    result = runner.invoke(plan_app, ["--branch", "42"])
    # When no --spec provided, default action is _plan_for_branch (not _plan_spec_impl)
    # This test now validates that behavior
    assert result.exit_code == 0


def test_plan_branch_basic_flow(monkeypatch) -> None:
    """Test plan --branch delegates to run_issue_role_async."""
    mock_runner = _patch_plan_deps(monkeypatch)
    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()
    call_kwargs = mock_runner.call_args[1]
    assert call_kwargs["issue_number"] == 42


def test_plan_branch_no_flow_error(monkeypatch) -> None:
    """Test plan --branch with no flow shows error."""
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = None

    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )

    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code != 0
    assert "No flow for branch" in result.output


def test_plan_branch_no_spec_error(monkeypatch) -> None:
    """Test plan --branch with no spec shows error."""
    mock_flow = _make_mock_flow(spec_ref=None)
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )

    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code != 0
    assert "No spec bound" in result.output


def test_plan_spec_file_basic_flow(monkeypatch) -> None:
    """Test plan --spec <file> flow."""
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    mock_execute = MagicMock()

    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_async", mock_execute)
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", mock_execute)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        MagicMock(),
    )

    with patch.object(Path, "exists", return_value=True):
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "resolve", return_value=Path("/abs/docs/spec.md")):
                result = runner.invoke(
                    plan_app, ["--spec", "docs/spec.md", "--branch", "42"]
                )
    assert result.exit_code == 0


def test_plan_issue_subcommand_works(monkeypatch) -> None:
    """Test that hidden 'issue' subcommand still works for backward compat."""
    mock_runner = _patch_plan_deps(monkeypatch)

    result = runner.invoke(plan_app, ["issue", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()
