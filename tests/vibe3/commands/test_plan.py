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
    mock_resolve = MagicMock()

    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_async", mock_async)
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", mock_sync)
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )
    return mock_async


def test_plan_help_shows_options() -> None:
    result = runner.invoke(plan_app, ["--help"])
    assert result.exit_code == 0
    # Strip ANSI codes for reliable assertion
    clean_output = result.output.replace("\x1b[1m", "").replace("\x1b[0m", "")
    assert "--branch" in clean_output
    assert "--spec" in clean_output


def test_plan_spec_uses_flow_spec_ref(monkeypatch) -> None:
    """Test plan --branch without --spec delegates to execute_spec_plan_async."""
    mock_runner = _patch_plan_deps(
        monkeypatch, mock_flow=_make_mock_flow(spec_ref="@task-42/spec.md")
    )
    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()


def test_plan_branch_basic_flow(monkeypatch) -> None:
    """Test plan --branch delegates to execute_spec_plan_async."""
    mock_runner = _patch_plan_deps(monkeypatch)
    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()
    call_kwargs = mock_runner.call_args[1]
    assert call_kwargs["issue_number"] == 42


def test_plan_no_arg_defaults_to_current_branch(monkeypatch) -> None:
    """Test plan without --branch uses current branch."""
    mock_runner = _patch_plan_deps(monkeypatch)
    mock_resolve = MagicMock(return_value="task/issue-42")
    monkeypatch.setattr("vibe3.commands.plan.resolve_branch_arg", mock_resolve)

    result = runner.invoke(plan_app, [])

    assert result.exit_code == 0
    mock_resolve.assert_called_once_with(None)
    mock_runner.assert_called_once()


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


def test_plan_no_arg_no_flow_error(monkeypatch) -> None:
    """Test plan without --branch and no flow shows clear error."""
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = None

    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "feature/no-flow"
    )

    result = runner.invoke(plan_app, [])
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


def test_plan_dry_run_branch(monkeypatch) -> None:
    """Test plan --branch --dry-run returns exit_code=0 without async dispatch."""
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_async = MagicMock()
    mock_sync = MagicMock()
    mock_resolve = MagicMock()

    # Mock create_codeagent_command and CodeagentExecutionService
    mock_command = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True

    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_async", mock_async)
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", mock_sync)
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr("vibe3.commands.plan.create_codeagent_command", mock_command)
    monkeypatch.setattr(
        "vibe3.commands.plan.CodeagentExecutionService",
        lambda cfg: MagicMock(execute_sync=lambda cmd: mock_result),
    )

    result = runner.invoke(plan_app, ["--branch", "42", "--dry-run"])
    assert result.exit_code == 0
    # Should NOT call async dispatch
    mock_async.assert_not_called()
    # Should create command with dry_run=True
    mock_command.assert_called_once()
    call_kwargs = mock_command.call_args[1]
    assert call_kwargs["dry_run"] is True


def test_plan_show_prompt_propagates(monkeypatch) -> None:
    """Test plan --branch --dry-run --show-prompt passes show_prompt=True."""
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_resolve = MagicMock()

    # Mock create_codeagent_command and CodeagentExecutionService
    mock_command = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True

    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr("vibe3.commands.plan.create_codeagent_command", mock_command)
    monkeypatch.setattr(
        "vibe3.commands.plan.CodeagentExecutionService",
        lambda cfg: MagicMock(execute_sync=lambda cmd: mock_result),
    )

    result = runner.invoke(plan_app, ["--branch", "42", "--dry-run", "--show-prompt"])
    assert result.exit_code == 0
    # Should create command with show_prompt=True
    mock_command.assert_called_once()
    call_kwargs = mock_command.call_args[1]
    assert call_kwargs["show_prompt"] is True


def test_plan_async_shows_tmux_info(monkeypatch) -> None:
    """Test plan --branch (async) shows tmux session and log path."""
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_result = MagicMock()
    mock_result.tmux_session = "vibe3-planner-issue-42"
    mock_result.log_path = "/path/to/log.md"

    mock_async = MagicMock(return_value=mock_result)
    mock_resolve = MagicMock()

    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_async", mock_async)
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )

    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code == 0
    # Should display tmux and log info
    assert "tmux: vibe3-planner-issue-42" in result.output
    assert "log: /path/to/log.md" in result.output
