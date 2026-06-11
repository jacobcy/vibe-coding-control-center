"""Tests for plan command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.plan import app as plan_app

runner = CliRunner(env={"NO_COLOR": "1"})


def _ensure_lazy_imports_populated() -> None:
    """Force vibe3.roles lazy import cache to populate with real values.

    Must be called BEFORE patching vibe3.roles.plan source module.
    Without this, monkeypatch.setattr on the cache triggers __getattr__
    which reads from the (already-mocked) source, caching the mock.
    monkeypatch.undo then restores the mock instead of the real function.
    """
    import vibe3.roles

    # Access each symbol to trigger __getattr__ and cache the real value
    _ = vibe3.roles.resolve_spec_plan_input
    _ = vibe3.roles.execute_spec_plan_async
    _ = vibe3.roles.execute_spec_plan_sync


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


def _patch_plan_deps(
    monkeypatch, mock_flow: MagicMock | None = None
) -> tuple[MagicMock, MagicMock]:
    """Patch all plan command external dependencies.

    Returns:
        Tuple of (mock_async, mock_sync) for verification in tests.
    """
    _ensure_lazy_imports_populated()

    if mock_flow is None:
        mock_flow = _make_mock_flow()

    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_async = MagicMock()
    mock_sync = MagicMock()
    mock_resolve = MagicMock()
    # Create a proper return value for resolve_spec_plan_input
    mock_spec_input = MagicMock()
    mock_spec_input.request = MagicMock()
    mock_resolve.return_value = mock_spec_input

    # Mock config for both command layer and domain handler
    mock_config = MagicMock()
    mock_config.plan.agent_config.backend = None
    mock_config.plan.agent_config.model = None
    mock_config.plan.agent_config.agent = None
    mock_config.plan.agent_config.timeout_seconds = 3600

    # Mock at roles lazy import cache BEFORE source to
    # ensure monkeypatch saves real function as old value.
    monkeypatch.setattr(
        "vibe3.roles.resolve_spec_plan_input",
        mock_resolve,
    )
    monkeypatch.setattr(
        "vibe3.roles.execute_spec_plan_async",
        mock_async,
    )
    monkeypatch.setattr(
        "vibe3.roles.execute_spec_plan_sync",
        mock_sync,
    )
    # Mock at roles.plan source module
    monkeypatch.setattr(
        "vibe3.roles.plan.resolve_spec_plan_input",
        mock_resolve,
    )
    monkeypatch.setattr(
        "vibe3.roles.plan.execute_spec_plan_async",
        mock_async,
    )
    monkeypatch.setattr(
        "vibe3.roles.plan.execute_spec_plan_sync",
        mock_sync,
    )
    # Mock at command layer (where functions are imported)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        mock_resolve,
    )
    # Mock config loader for domain handler
    monkeypatch.setattr(
        "vibe3.config.config_loader.load_config_for_role",
        lambda *a, **kw: mock_config,
    )
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg",
        lambda _: "task/issue-42",
    )
    return mock_async, mock_sync


def test_plan_help_shows_options() -> None:
    result = runner.invoke(plan_app, ["--help"])
    assert result.exit_code == 0
    # Strip ANSI codes for reliable assertion
    clean_output = result.output.replace("\x1b[1m", "").replace("\x1b[0m", "")
    assert "--branch" in clean_output
    assert "--spec" in clean_output
    # New options from issue #2023
    assert "--agent" in clean_output
    assert "--backend" in clean_output
    assert "--model" in clean_output
    assert "--fresh-session" in clean_output


def test_plan_spec_uses_flow_spec_ref(monkeypatch) -> None:
    """Test plan --branch without --spec delegates to execute_spec_plan_async."""
    mock_runner, _ = _patch_plan_deps(
        monkeypatch, mock_flow=_make_mock_flow(spec_ref="@task-42/spec.md")
    )
    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()


def test_plan_branch_basic_flow(monkeypatch) -> None:
    """Test plan --branch delegates to execute_spec_plan_async."""
    mock_runner, _ = _patch_plan_deps(monkeypatch)
    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()
    call_kwargs = mock_runner.call_args[1]
    assert call_kwargs["issue_number"] == 42


def test_plan_no_arg_defaults_to_current_branch(monkeypatch) -> None:
    """Test plan without --branch uses current branch."""
    mock_runner, _ = _patch_plan_deps(monkeypatch)
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
    _ensure_lazy_imports_populated()

    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    mock_execute = MagicMock()
    mock_resolve = MagicMock()
    # Create a proper return value for resolve_spec_plan_input
    mock_spec_input = MagicMock()
    mock_spec_input.request = MagicMock()
    mock_resolve.return_value = mock_spec_input

    # Cache before source
    monkeypatch.setattr("vibe3.roles.execute_spec_plan_async", mock_execute)
    monkeypatch.setattr("vibe3.roles.execute_spec_plan_sync", mock_execute)
    monkeypatch.setattr("vibe3.roles.resolve_spec_plan_input", mock_resolve)
    # Source
    monkeypatch.setattr("vibe3.roles.plan.execute_spec_plan_async", mock_execute)
    monkeypatch.setattr("vibe3.roles.plan.execute_spec_plan_sync", mock_execute)
    monkeypatch.setattr("vibe3.roles.plan.resolve_spec_plan_input", mock_resolve)
    # Command layer
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr(
        "vibe3.commands.plan.FlowService",
        lambda: mock_flow_service,
    )
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg",
        lambda _: "task/issue-42",
    )
    # Mock load_config_and_validate_model since we refactored config loading
    mock_config = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.plan.load_config_and_validate_model",
        lambda *a, **kw: mock_config,
    )
    # Mock config loader for domain handler
    monkeypatch.setattr(
        "vibe3.config.config_loader.load_config_for_role",
        lambda *a, **kw: mock_config,
    )

    with patch.object(Path, "exists", return_value=True):
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "resolve", return_value=Path("/abs/docs/spec.md")):
                result = runner.invoke(
                    plan_app,
                    ["--spec", "docs/spec.md", "--branch", "42"],
                )
    assert result.exit_code == 0


def test_plan_issue_subcommand_works(monkeypatch) -> None:
    """Test that hidden 'issue' subcommand still works for backward compat."""
    mock_runner, _ = _patch_plan_deps(monkeypatch)

    result = runner.invoke(plan_app, ["issue", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()


def test_plan_dry_run_branch(monkeypatch) -> None:
    """Test plan --branch --dry-run returns exit_code=0 without async dispatch."""
    _ensure_lazy_imports_populated()

    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_resolve = MagicMock()
    # Create a proper return value for resolve_spec_plan_input
    mock_spec_input = MagicMock()
    mock_spec_input.request = MagicMock()
    mock_resolve.return_value = mock_spec_input

    # Mock create_codeagent_command and CodeagentExecutionService
    mock_command = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True

    # Mock config
    mock_config = MagicMock()

    # Don't mock execute_spec_plan_sync - let it call create_codeagent_command
    # Cache before source for resolve_spec_plan_input
    monkeypatch.setattr("vibe3.roles.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr("vibe3.roles.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr(
        "vibe3.commands.plan.FlowService",
        lambda: mock_flow_service,
    )
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg",
        lambda _: "task/issue-42",
    )
    monkeypatch.setattr(
        "vibe3.roles.plan.create_codeagent_command",
        mock_command,
    )
    monkeypatch.setattr(
        "vibe3.roles.plan.CodeagentExecutionService",
        lambda cfg: MagicMock(
            execute_sync=lambda cmd: mock_result,
        ),
    )
    # Mock config loader for domain handler
    monkeypatch.setattr(
        "vibe3.config.config_loader.load_config_for_role",
        lambda *a, **kw: mock_config,
    )

    result = runner.invoke(plan_app, ["--branch", "42", "--dry-run"])
    assert result.exit_code == 0
    # Should create command with dry_run=True
    mock_command.assert_called_once()
    call_kwargs = mock_command.call_args[1]
    assert call_kwargs["dry_run"] is True


def test_plan_show_prompt_propagates(monkeypatch) -> None:
    """Test plan --branch --dry-run --show-prompt passes show_prompt=True."""
    _ensure_lazy_imports_populated()

    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_resolve = MagicMock()
    # Create a proper return value for resolve_spec_plan_input
    mock_spec_input = MagicMock()
    mock_spec_input.request = MagicMock()
    mock_resolve.return_value = mock_spec_input

    # Mock create_codeagent_command and CodeagentExecutionService
    mock_command = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True

    # Mock config
    mock_config = MagicMock()

    # Cache before source for resolve_spec_plan_input
    monkeypatch.setattr("vibe3.roles.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr("vibe3.roles.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", mock_resolve)
    monkeypatch.setattr(
        "vibe3.commands.plan.FlowService",
        lambda: mock_flow_service,
    )
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg",
        lambda _: "task/issue-42",
    )
    monkeypatch.setattr(
        "vibe3.roles.plan.create_codeagent_command",
        mock_command,
    )
    monkeypatch.setattr(
        "vibe3.roles.plan.CodeagentExecutionService",
        lambda cfg: MagicMock(
            execute_sync=lambda cmd: mock_result,
        ),
    )
    # Mock config loader for domain handler
    monkeypatch.setattr(
        "vibe3.config.config_loader.load_config_for_role",
        lambda *a, **kw: mock_config,
    )

    result = runner.invoke(plan_app, ["--branch", "42", "--dry-run", "--show-prompt"])
    assert result.exit_code == 0
    # Should create command with show_prompt=True
    mock_command.assert_called_once()
    call_kwargs = mock_command.call_args[1]
    assert call_kwargs["show_prompt"] is True


def test_plan_async_shows_tmux_info(monkeypatch) -> None:
    """Test plan --branch (async) shows tmux session and log path."""
    _ensure_lazy_imports_populated()

    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_result = MagicMock()
    mock_result.tmux_session = "vibe3-planner-issue-42"
    mock_result.log_path = "/path/to/log.md"

    mock_async = MagicMock(return_value=mock_result)
    mock_resolve = MagicMock()
    # Create a proper return value for resolve_spec_plan_input
    mock_spec_input = MagicMock()
    mock_spec_input.request = MagicMock()
    mock_resolve.return_value = mock_spec_input

    # Mock config
    mock_config = MagicMock()

    # Cache before source
    monkeypatch.setattr("vibe3.roles.execute_spec_plan_async", mock_async)
    monkeypatch.setattr("vibe3.roles.resolve_spec_plan_input", mock_resolve)
    # Source
    monkeypatch.setattr("vibe3.roles.plan.execute_spec_plan_async", mock_async)
    monkeypatch.setattr("vibe3.roles.plan.resolve_spec_plan_input", mock_resolve)
    # Command layer
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        mock_resolve,
    )
    monkeypatch.setattr(
        "vibe3.commands.plan.FlowService",
        lambda: mock_flow_service,
    )
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg",
        lambda _: "task/issue-42",
    )
    # Mock config loader for domain handler
    monkeypatch.setattr(
        "vibe3.config.config_loader.load_config_for_role",
        lambda *a, **kw: mock_config,
    )

    result = runner.invoke(plan_app, ["--branch", "42"])
    assert result.exit_code == 0
    # Should display tmux and log info
    assert "tmux session: vibe3-planner-issue-42" in result.output
    assert "log: /path/to/log.md" in result.output


def test_plan_agent_option_propagates(monkeypatch) -> None:
    """Test plan --agent foo propagates to execute_spec_plan_sync."""
    _, mock_sync = _patch_plan_deps(monkeypatch)

    result = runner.invoke(plan_app, ["--branch", "42", "--no-async", "--agent", "foo"])
    assert result.exit_code == 0
    mock_sync.assert_called_once()
    call_kwargs = mock_sync.call_args[1]
    assert call_kwargs["agent"] == "foo"


def test_plan_backend_option_propagates(monkeypatch) -> None:
    """Test plan --backend claude propagates to execute_spec_plan_sync."""
    _, mock_sync = _patch_plan_deps(monkeypatch)

    result = runner.invoke(
        plan_app, ["--branch", "42", "--no-async", "--backend", "claude"]
    )
    assert result.exit_code == 0
    mock_sync.assert_called_once()
    call_kwargs = mock_sync.call_args[1]
    assert call_kwargs["backend"] == "claude"


def test_plan_model_option_propagates(monkeypatch) -> None:
    """Test plan --model claude-opus-4-8 propagates to execute_spec_plan_sync."""
    _, mock_sync = _patch_plan_deps(monkeypatch)

    result = runner.invoke(
        plan_app,
        [
            "--branch",
            "42",
            "--no-async",
            "--backend",
            "claude",
            "--model",
            "claude-opus-4-8",
        ],
    )
    assert result.exit_code == 0
    mock_sync.assert_called_once()
    call_kwargs = mock_sync.call_args[1]
    assert call_kwargs["model"] == "claude-opus-4-8"


def test_plan_fresh_session_propagates(monkeypatch) -> None:
    """Test plan --fresh-session propagates to execute_spec_plan_sync."""
    _, mock_sync = _patch_plan_deps(monkeypatch)

    result = runner.invoke(
        plan_app, ["--branch", "42", "--no-async", "--fresh-session"]
    )
    assert result.exit_code == 0
    mock_sync.assert_called_once()
    call_kwargs = mock_sync.call_args[1]
    assert call_kwargs["fresh_session"] is True


def test_plan_model_with_config_backend_succeeds(monkeypatch) -> None:
    """Test --model works when config provides backend (the #2435 fix).

    When user has backend: "claude" in settings.yaml and runs:
      vibe3 plan --model opus
    This should succeed -- config provides backend, CLI provides model.
    """
    _ensure_lazy_imports_populated()

    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    mock_sync = MagicMock()
    mock_resolve = MagicMock()
    # Create a proper return value for resolve_spec_plan_input
    mock_spec_input = MagicMock()
    mock_spec_input.request = MagicMock()
    mock_resolve.return_value = mock_spec_input

    # Cache before source
    monkeypatch.setattr("vibe3.roles.execute_spec_plan_sync", mock_sync)
    monkeypatch.setattr("vibe3.roles.resolve_spec_plan_input", mock_resolve)
    # Source
    monkeypatch.setattr("vibe3.roles.plan.execute_spec_plan_sync", mock_sync)
    monkeypatch.setattr("vibe3.roles.plan.resolve_spec_plan_input", mock_resolve)
    # Command layer
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        mock_resolve,
    )
    monkeypatch.setattr(
        "vibe3.commands.plan.FlowService",
        lambda: mock_flow_service,
    )
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg",
        lambda _: "task/issue-42",
    )

    # Mock config with backend set (simulating settings.yaml)
    mock_config = MagicMock()
    mock_config.plan.agent_config.backend = "claude"
    mock_config.plan.agent_config.model = None
    mock_config.plan.agent_config.agent = None
    mock_config.plan.agent_config.timeout_seconds = 3600
    monkeypatch.setattr(
        "vibe3.commands.plan.load_config_and_validate_model",
        lambda *a, **kw: mock_config,
    )
    # Mock config loader for domain handler
    monkeypatch.setattr(
        "vibe3.config.config_loader.load_config_for_role",
        lambda *a, **kw: mock_config,
    )

    result = runner.invoke(
        plan_app, ["--branch", "42", "--no-async", "--model", "opus"]
    )
    assert result.exit_code == 0, f"Expected success but got: {result.output}"
    mock_sync.assert_called_once()
    call_kwargs = mock_sync.call_args[1]
    assert call_kwargs["model"] == "opus"
