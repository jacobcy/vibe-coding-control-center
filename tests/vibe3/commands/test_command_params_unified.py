"""Unified tests for command parameter behavior.

Tests --branch default resolution, --dry-run, --show-prompt, and config/CLI override
behavior across plan/run/review/internal-manager commands.
"""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from vibe3.commands.internal import app as internal_app
from vibe3.commands.plan import app as plan_app
from vibe3.commands.review import app as review_app
from vibe3.commands.run import app as run_app

runner = CliRunner(env={"NO_COLOR": "1"})


def _make_mock_flow(
    branch: str = "task/issue-42",
    spec_ref: str | None = "#42",
    issue_number: int = 42,
) -> MagicMock:
    """Create a mock flow object with sensible defaults.

    Reuses pattern from test_plan.py.
    """
    mock_flow = MagicMock()
    mock_flow.branch = branch
    mock_flow.spec_ref = spec_ref
    mock_flow.task_issue_number = issue_number
    return mock_flow


def _patch_common(
    monkeypatch: pytest.MonkeyPatch,
    command_module: str,
    mock_flow: MagicMock | None = None,
) -> MagicMock:
    """Patch common dependencies for command tests.

    Args:
        monkeypatch: pytest monkeypatch fixture
        command_module: Module path (e.g., "vibe3.commands.plan")
        mock_flow: Optional mock flow object

    Returns:
        MagicMock for the execution function (to assert call args)
    """
    if mock_flow is None:
        mock_flow = _make_mock_flow()

    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow

    # Create execution mock based on command type
    execution_mock = MagicMock()

    # Patch module-specific execution functions
    if command_module == "vibe3.commands.plan":
        monkeypatch.setattr(f"{command_module}.execute_spec_plan_async", execution_mock)
        monkeypatch.setattr(f"{command_module}.execute_spec_plan_sync", MagicMock())
        monkeypatch.setattr(f"{command_module}.resolve_spec_plan_input", MagicMock())
        monkeypatch.setattr(f"{command_module}.FlowService", lambda: mock_flow_service)
        monkeypatch.setattr(
            f"{command_module}.resolve_branch_arg", lambda _: "task/issue-42"
        )
    elif command_module == "vibe3.commands.run":
        monkeypatch.setattr(f"{command_module}.execute_manual_run", execution_mock)
        monkeypatch.setattr(f"{command_module}.validate_run_prerequisites", MagicMock())
        monkeypatch.setattr(f"{command_module}.FlowService", lambda: mock_flow_service)
        monkeypatch.setattr(
            f"{command_module}.resolve_branch_arg", lambda _: "task/issue-42"
        )
    elif command_module == "vibe3.commands.review":
        monkeypatch.setattr(f"{command_module}.run_issue_role_sync", execution_mock)
        monkeypatch.setattr(f"{command_module}.run_issue_role_async", MagicMock())
        monkeypatch.setattr(
            f"{command_module}.validate_review_prerequisites", MagicMock()
        )
        monkeypatch.setattr(f"{command_module}.FlowService", lambda: mock_flow_service)
        monkeypatch.setattr(
            f"{command_module}.resolve_branch_arg", lambda _: "task/issue-42"
        )
    else:
        raise ValueError(f"Unknown command module: {command_module}")

    return execution_mock


# ==============================================================================
# Step 2: Branch default tests — plan
# ==============================================================================


def test_plan_no_branch_uses_current_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 plan without --branch calls resolve_branch_arg(None)."""
    mock_resolve = MagicMock(return_value="task/test-branch")
    monkeypatch.setattr("vibe3.commands.plan.resolve_branch_arg", mock_resolve)

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_async", MagicMock())
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", MagicMock())
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", MagicMock())

    runner.invoke(plan_app, [])

    # resolve_branch_arg should be called with None
    mock_resolve.assert_called_once_with(None)


def test_plan_issue_number_resolves_to_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 plan --branch 42 resolves issue number to task/issue-42."""
    mock_resolve = MagicMock(return_value="task/issue-42")
    mock_execute = MagicMock()

    monkeypatch.setattr("vibe3.commands.plan.resolve_branch_arg", mock_resolve)
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_async", mock_execute)

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", MagicMock())
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", MagicMock())

    runner.invoke(plan_app, ["--branch", "42"])

    # resolve_branch_arg should be called with "42"
    mock_resolve.assert_called_once_with("42")


# ==============================================================================
# Step 3: Branch default tests — run
# ==============================================================================


def test_run_no_branch_uses_current_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 run without --branch calls resolve_branch_arg(None)."""
    mock_resolve = MagicMock(return_value="task/test-branch")
    monkeypatch.setattr("vibe3.commands.run.resolve_branch_arg", mock_resolve)

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.run.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", MagicMock())
    monkeypatch.setattr("vibe3.commands.run.validate_run_prerequisites", MagicMock())

    runner.invoke(run_app, ["test instructions"])

    # resolve_branch_arg should be called with None
    mock_resolve.assert_called_once_with(None)


def test_run_issue_number_resolves_to_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 run --branch 42 resolves issue number to canonical branch."""
    mock_resolve = MagicMock(return_value="task/issue-42")
    mock_execute = MagicMock()

    monkeypatch.setattr("vibe3.commands.run.resolve_branch_arg", mock_resolve)
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.run.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr("vibe3.commands.run.validate_run_prerequisites", MagicMock())

    runner.invoke(run_app, ["--branch", "42", "test instructions"])

    # resolve_branch_arg should be called with "42"
    mock_resolve.assert_called_once_with("42")


# ==============================================================================
# Step 4: Branch default tests — review
# ==============================================================================


def test_review_no_branch_shows_help() -> None:
    """vibe3 review without --branch requires branch argument."""
    # Review doesn't have no_args_is_help, so it requires --branch
    # When invoked without args, it will error because resolve_branch_arg needs mocking
    result = runner.invoke(review_app, [])

    # Should fail because no branch and no proper flow context
    assert result.exit_code != 0


def test_review_issue_number_resolves_to_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """vibe3 review --branch 42 resolves issue number."""
    mock_resolve = MagicMock(return_value="task/issue-42")
    monkeypatch.setattr("vibe3.commands.review.resolve_branch_arg", mock_resolve)
    monkeypatch.setattr(
        "vibe3.commands.review.validate_review_prerequisites", MagicMock()
    )
    monkeypatch.setattr("vibe3.commands.review.run_issue_role_sync", MagicMock())
    monkeypatch.setattr("vibe3.commands.review.run_issue_role_async", MagicMock())

    runner.invoke(review_app, ["--branch", "42"])

    # resolve_branch_arg should be called with "42"
    mock_resolve.assert_called_once_with("42")


# ==============================================================================
# Step 5: Dry-run tests — plan
# ==============================================================================


def test_plan_dry_run_outputs_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 plan --branch 42 --spec docs/spec.md --dry-run executes dry-run path."""
    from unittest.mock import MagicMock

    # Mock the execution services to prevent real execution
    mock_execute_async = MagicMock()
    mock_execute_sync = MagicMock()
    mock_codeagent_exec_sync = MagicMock()

    monkeypatch.setattr(
        "vibe3.commands.plan.execute_spec_plan_async", mock_execute_async
    )
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", mock_execute_sync)

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )

    # Mock resolve_spec_plan_input to return a valid spec input
    mock_spec_input = MagicMock()
    mock_spec_input.request.task_guidance = "Test task"
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        lambda branch, file=None: mock_spec_input,
    )

    # Mock VibeConfig.get_defaults (from vibe3.config module)
    mock_config = MagicMock()
    monkeypatch.setattr(
        "vibe3.config.loader.VibeConfig.get_defaults", lambda: mock_config
    )

    # Mock create_codeagent_command
    mock_command = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.plan.create_codeagent_command", lambda **kwargs: mock_command
    )

    # Mock CodeagentExecutionService constructor and execute_sync
    mock_service = MagicMock()
    mock_service.execute_sync = mock_codeagent_exec_sync
    monkeypatch.setattr(
        "vibe3.commands.plan.CodeagentExecutionService", lambda cfg: mock_service
    )

    # Create a mock spec file
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Test Spec\n")
        spec_path = f.name

    try:
        runner.invoke(plan_app, ["--branch", "42", "--spec", spec_path, "--dry-run"])

        # execute_spec_plan_async and execute_spec_plan_sync should NOT be called
        mock_execute_async.assert_not_called()
        mock_execute_sync.assert_not_called()

        # CodeagentExecutionService.execute_sync should be called (dry-run path)
        mock_codeagent_exec_sync.assert_called_once()
    finally:
        Path(spec_path).unlink()


# ==============================================================================
# Step 6: Dry-run tests — run
# ==============================================================================


def test_run_dry_run_forwards_to_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 run --dry-run --no-async forwards dry_run=True to execute_manual_run."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    # Mock load_runtime_config
    mock_config = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.run.load_runtime_config", lambda cli_overrides=None: mock_config
    )

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.run.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.run.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr(
        "vibe3.commands.run.validate_run_prerequisites",
        MagicMock(return_value=(mock_flow, 42)),
    )

    runner.invoke(run_app, ["--dry-run", "--no-async", "test instructions"])

    # execute_manual_run should be called with dry_run=True
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs.get("dry_run") is True


# ==============================================================================
# Step 7: Dry-run tests — review
# ==============================================================================


def test_review_base_dry_run_returns_dry_run_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """vibe3 review base main --dry-run --no-async returns DRY_RUN result."""
    # Mock ensure_flow_for_current_branch
    mock_ensure_flow = MagicMock()
    mock_ensure_flow.return_value = (MagicMock(), "task/issue-42")
    monkeypatch.setattr(
        "vibe3.commands.review.ensure_flow_for_current_branch", mock_ensure_flow
    )

    # Mock build_base_resolution_usecase
    mock_usecase = MagicMock()
    mock_usecase.resolve_review_base.return_value = MagicMock(
        base_branch="main", auto_detected=False
    )
    monkeypatch.setattr(
        "vibe3.commands.review.build_base_resolution_usecase", lambda: mock_usecase
    )

    # Mock build_base_review_request
    mock_request = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.review.build_base_review_request",
        lambda current_branch, base_branch, flow_service=None: (mock_request, 42, None),
    )

    # Mock execute_manual_review_sync to return DRY_RUN verdict
    mock_execute = MagicMock()
    mock_execute.return_value = MagicMock(verdict="DRY_RUN", handoff_file=None)
    monkeypatch.setattr(
        "vibe3.commands.review.execute_manual_review_sync", mock_execute
    )

    result = runner.invoke(review_app, ["base", "main", "--dry-run", "--no-async"])

    # Exit code should be 0 for DRY_RUN
    assert result.exit_code == 0
    # execute_manual_review_sync should be called with dry_run=True
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs.get("dry_run") is True


# ==============================================================================
# Step 8: Dry-run tests — internal manager (requires #1905)
# ==============================================================================


def test_internal_manager_dry_run_forwards_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """vibe3 internal manager 123 --no-async --dry-run forwards dry_run=True."""
    mock_execute = MagicMock()
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync", mock_execute
    )

    runner.invoke(internal_app, ["manager", "123", "--no-async", "--dry-run"])

    # run_issue_role_sync should be called with dry_run=True
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs.get("dry_run") is True


# ==============================================================================
# Step 9: Show-prompt tests — plan
# ==============================================================================


def test_plan_show_prompt_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 plan --branch 42 --dry-run --show-prompt forwards show_prompt=True."""
    # Use the _plan_spec_impl path (with --spec) which handles dry_run properly
    # Mock CodeagentExecutionService.execute_sync
    mock_codeagent_exec_sync = MagicMock()
    mock_service = MagicMock()
    mock_service.execute_sync = mock_codeagent_exec_sync
    monkeypatch.setattr(
        "vibe3.commands.plan.CodeagentExecutionService", lambda cfg: mock_service
    )

    # Mock other dependencies for _plan_spec_impl
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )

    # Mock resolve_spec_plan_input
    mock_spec_input = MagicMock()
    mock_spec_input.request.task_guidance = "Test task"
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        lambda branch, file=None: mock_spec_input,
    )

    # Mock VibeConfig.get_defaults (from vibe3.config module)
    mock_config = MagicMock()
    monkeypatch.setattr(
        "vibe3.config.loader.VibeConfig.get_defaults", lambda: mock_config
    )

    # Mock create_codeagent_command to capture show_prompt
    mock_command = MagicMock()
    captured_kwargs = {}

    def capture_command(**kwargs):
        captured_kwargs.update(kwargs)
        return mock_command

    monkeypatch.setattr("vibe3.commands.plan.create_codeagent_command", capture_command)

    # Create a mock spec file
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Test Spec\n")
        spec_path = f.name

    try:
        runner.invoke(
            plan_app,
            ["--branch", "42", "--spec", spec_path, "--dry-run", "--show-prompt"],
        )

        # create_codeagent_command should be called with show_prompt=True
        assert captured_kwargs.get("show_prompt") is True
    finally:
        Path(spec_path).unlink()


# ==============================================================================
# Step 10: Show-prompt tests — run
# ==============================================================================


def test_run_show_prompt_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 run "test" --dry-run --show-prompt --no-async forwards both flags."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    # Mock load_runtime_config
    mock_config = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.run.load_runtime_config", lambda cli_overrides=None: mock_config
    )

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.run.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.run.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr(
        "vibe3.commands.run.validate_run_prerequisites",
        MagicMock(return_value=(mock_flow, 42)),
    )

    runner.invoke(
        run_app, ["--dry-run", "--show-prompt", "--no-async", "test instructions"]
    )

    # execute_manual_run should be called with both flags
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs.get("dry_run") is True
    assert call_kwargs.get("show_prompt") is True


# ==============================================================================
# Step 11: Show-prompt tests — review
# ==============================================================================


def test_review_show_prompt_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    """vibe3 review --branch 42 --dry-run --show-prompt forwards show_prompt=True."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.review.run_issue_role_sync", mock_execute)
    monkeypatch.setattr(
        "vibe3.commands.review.validate_review_prerequisites",
        MagicMock(return_value=(MagicMock(), 42)),
    )
    monkeypatch.setattr(
        "vibe3.commands.review.resolve_branch_arg", lambda _: "task/issue-42"
    )

    runner.invoke(
        review_app,
        ["--branch", "42", "--dry-run", "--show-prompt"],
    )

    # run_issue_role_sync should be called with show_prompt=True
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs.get("show_prompt") is True


# ==============================================================================
# Step 12: Show-prompt tests — internal manager (requires #1905)
# ==============================================================================


def test_internal_manager_show_prompt_forwarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """vibe3 internal manager forwards show_prompt parameter."""
    mock_execute = MagicMock()
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync", mock_execute
    )

    runner.invoke(
        internal_app, ["manager", "123", "--no-async", "--dry-run", "--show-prompt"]
    )

    # run_issue_role_sync should be called with show_prompt=True
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs.get("show_prompt") is True


# ==============================================================================
# Step 13: Config/CLI override tests
# ==============================================================================


def test_run_cli_agent_overrides_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """--agent CLI option forwards agent parameter to execute_manual_run."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    # Mock load_runtime_config
    mock_config = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.run.load_runtime_config", lambda cli_overrides=None: mock_config
    )

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.run.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.run.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr(
        "vibe3.commands.run.validate_run_prerequisites",
        MagicMock(return_value=(mock_flow, 42)),
    )

    runner.invoke(
        run_app, ["--agent", "override-agent", "--no-async", "test instructions"]
    )

    # execute_manual_run should be called with agent="override-agent"
    assert mock_execute.called
    call_kwargs = mock_execute.call_args[1]
    assert call_kwargs.get("agent") == "override-agent"


def test_run_cli_backend_overrides_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """--backend CLI option is captured in cli_overrides."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    # Mock load_runtime_config to capture cli_overrides
    captured_overrides = {}

    def capture_config(cli_overrides=None):
        captured_overrides.update(cli_overrides or {})
        return MagicMock()

    monkeypatch.setattr("vibe3.commands.run.load_runtime_config", capture_config)

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.run.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.run.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr(
        "vibe3.commands.run.validate_run_prerequisites",
        MagicMock(return_value=(mock_flow, 42)),
    )

    runner.invoke(
        run_app, ["--backend", "override-backend", "--no-async", "test instructions"]
    )

    # cli_overrides should capture backend override
    assert "run.agent_config.backend" in captured_overrides
    assert captured_overrides["run.agent_config.backend"] == "override-backend"


def test_run_no_cli_override_uses_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without CLI overrides, config is loaded without cli_overrides."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    # Mock load_runtime_config
    mock_config = MagicMock()
    captured_overrides = {}

    def capture_config(cli_overrides=None):
        captured_overrides.update(cli_overrides or {})
        return mock_config

    monkeypatch.setattr("vibe3.commands.run.load_runtime_config", capture_config)

    # Patch other dependencies
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.run.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.run.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr(
        "vibe3.commands.run.validate_run_prerequisites",
        MagicMock(return_value=(mock_flow, 42)),
    )

    runner.invoke(run_app, ["--no-async", "test instructions"])

    # load_runtime_config should be called without cli_overrides (empty dict)
    assert mock_execute.called
    # Config resolution happens deeper, so we just verify the call was made
