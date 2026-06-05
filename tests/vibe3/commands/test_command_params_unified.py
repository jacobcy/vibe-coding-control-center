"""Unified tests for command parameter behavior.

Tests --branch default resolution, --dry-run, --show-prompt, and config/CLI override
behavior across plan/run/review/internal-manager commands.
"""

from pathlib import Path
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
    mock_flow = MagicMock()
    mock_flow.branch = branch
    mock_flow.spec_ref = spec_ref
    mock_flow.task_issue_number = issue_number
    return mock_flow


@pytest.fixture
def mock_plan_deps(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Silence plan command baseline dependencies."""
    mock_flow = _make_mock_flow()
    mock_flow_service = MagicMock()
    mock_flow_service.get_flow_status.return_value = mock_flow
    monkeypatch.setattr("vibe3.commands.plan.FlowService", lambda: mock_flow_service)
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_async", MagicMock())
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", MagicMock())
    monkeypatch.setattr("vibe3.commands.plan.resolve_spec_plan_input", MagicMock())
    return {"flow": mock_flow}


@pytest.fixture
def mock_run_deps(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Silence run command baseline dependencies."""
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
    monkeypatch.setattr(
        "vibe3.commands.run.load_runtime_config", lambda cli_overrides=None: MagicMock()
    )
    return {"flow": mock_flow}


@pytest.fixture
def mock_review_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence review command baseline dependencies."""
    monkeypatch.setattr(
        "vibe3.commands.review.resolve_branch_arg", lambda _: "task/issue-42"
    )
    monkeypatch.setattr(
        "vibe3.commands.review.validate_review_prerequisites",
        MagicMock(return_value=(MagicMock(), 42)),
    )
    monkeypatch.setattr("vibe3.commands.review.run_issue_role_sync", MagicMock())
    monkeypatch.setattr("vibe3.commands.review.run_issue_role_async", MagicMock())


# ==============================================================================
# Branch default resolution tests
# ==============================================================================


def test_plan_no_branch_uses_current_branch(
    monkeypatch: pytest.MonkeyPatch, mock_plan_deps: dict
) -> None:
    """vibe3 plan without --branch calls resolve_branch_arg(None)."""
    mock_resolve = MagicMock(return_value="task/test-branch")
    monkeypatch.setattr("vibe3.commands.plan.resolve_branch_arg", mock_resolve)

    runner.invoke(plan_app, [])

    mock_resolve.assert_called_once_with(None)


def test_plan_issue_number_resolves_to_branch(
    monkeypatch: pytest.MonkeyPatch, mock_plan_deps: dict
) -> None:
    """vibe3 plan --branch 42 passes "42" to resolve_branch_arg."""
    mock_resolve = MagicMock(return_value="task/issue-42")
    monkeypatch.setattr("vibe3.commands.plan.resolve_branch_arg", mock_resolve)

    runner.invoke(plan_app, ["--branch", "42"])

    mock_resolve.assert_called_once_with("42")


def test_run_no_branch_uses_current_branch(
    monkeypatch: pytest.MonkeyPatch, mock_run_deps: dict
) -> None:
    """vibe3 run without --branch calls resolve_branch_arg(None)."""
    mock_resolve = MagicMock(return_value="task/test-branch")
    monkeypatch.setattr("vibe3.commands.run.resolve_branch_arg", mock_resolve)
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", MagicMock())

    runner.invoke(run_app, ["test instructions"])

    mock_resolve.assert_called_once_with(None)


def test_run_issue_number_resolves_to_branch(
    monkeypatch: pytest.MonkeyPatch, mock_run_deps: dict
) -> None:
    """vibe3 run --branch 42 passes "42" to resolve_branch_arg."""
    mock_resolve = MagicMock(return_value="task/issue-42")
    monkeypatch.setattr("vibe3.commands.run.resolve_branch_arg", mock_resolve)
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", MagicMock())

    runner.invoke(run_app, ["--branch", "42", "test instructions"])

    mock_resolve.assert_called_once_with("42")


def test_review_no_branch_shows_help() -> None:
    """vibe3 review without args fails — requires branch context."""
    result = runner.invoke(review_app, [])

    assert result.exit_code != 0
    assert result.exception is not None


def test_review_issue_number_resolves_to_branch(
    monkeypatch: pytest.MonkeyPatch, mock_review_deps: None
) -> None:
    """vibe3 review --branch 42 passes "42" to resolve_branch_arg."""
    mock_resolve = MagicMock(return_value="task/issue-42")
    monkeypatch.setattr("vibe3.commands.review.resolve_branch_arg", mock_resolve)

    runner.invoke(review_app, ["--branch", "42"])

    mock_resolve.assert_called_once_with("42")


# ==============================================================================
# Dry-run flag forwarding tests
# ==============================================================================


def test_plan_dry_run_outputs_summary(
    monkeypatch: pytest.MonkeyPatch, mock_plan_deps: dict, tmp_path: Path
) -> None:
    """vibe3 plan --dry-run uses CodeagentExecutionService, not execute_spec_plan."""
    mock_execute_async = MagicMock()
    mock_execute_sync = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.plan.execute_spec_plan_async", mock_execute_async
    )
    monkeypatch.setattr("vibe3.commands.plan.execute_spec_plan_sync", mock_execute_sync)

    mock_spec_input = MagicMock()
    mock_spec_input.request.task_guidance = "Test task"
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        lambda branch, file=None: mock_spec_input,
    )
    monkeypatch.setattr(
        "vibe3.config.loader.VibeConfig.get_defaults", lambda: MagicMock()
    )
    monkeypatch.setattr(
        "vibe3.commands.plan.create_codeagent_command", lambda **kwargs: MagicMock()
    )

    mock_codeagent_exec_sync = MagicMock()
    mock_service = MagicMock()
    mock_service.execute_sync = mock_codeagent_exec_sync
    monkeypatch.setattr(
        "vibe3.commands.plan.CodeagentExecutionService", lambda cfg: mock_service
    )

    spec_file = tmp_path / "spec.md"
    spec_file.write_text("# Test Spec\n")

    runner.invoke(plan_app, ["--branch", "42", "--spec", str(spec_file), "--dry-run"])

    mock_execute_async.assert_not_called()
    mock_execute_sync.assert_not_called()
    mock_codeagent_exec_sync.assert_called_once()


def test_run_dry_run_forwards_to_execution(
    monkeypatch: pytest.MonkeyPatch, mock_run_deps: dict
) -> None:
    """vibe3 run --dry-run forwards dry_run=True to execute_manual_run."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    runner.invoke(run_app, ["--dry-run", "--no-async", "test instructions"])

    assert mock_execute.called
    assert mock_execute.call_args.kwargs.get("dry_run") is True


def test_review_base_dry_run_returns_dry_run_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """vibe3 review base --dry-run returns DRY_RUN verdict, passes dry_run=True."""
    mock_ensure_flow = MagicMock(return_value=(MagicMock(), "task/issue-42"))
    monkeypatch.setattr(
        "vibe3.commands.review.ensure_flow_for_current_branch", mock_ensure_flow
    )

    mock_usecase = MagicMock()
    mock_usecase.resolve_review_base.return_value = MagicMock(
        base_branch="main", auto_detected=False
    )
    monkeypatch.setattr(
        "vibe3.commands.review.build_base_resolution_usecase", lambda: mock_usecase
    )

    mock_request = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.review.build_base_review_request",
        lambda current_branch, base_branch, flow_service=None: (mock_request, 42, None),
    )

    mock_result = MagicMock(verdict="DRY_RUN", handoff_file=None)
    mock_execute = MagicMock(return_value=mock_result)
    monkeypatch.setattr(
        "vibe3.commands.review.execute_manual_review_sync", mock_execute
    )

    result = runner.invoke(review_app, ["base", "main", "--dry-run", "--no-async"])

    assert result.exit_code == 0
    assert mock_execute.called
    assert mock_execute.call_args.kwargs.get("dry_run") is True


def test_internal_manager_dry_run_forwards_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """vibe3 internal manager --dry-run forwards dry_run=True."""
    mock_execute = MagicMock()
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync", mock_execute
    )

    runner.invoke(internal_app, ["manager", "123", "--no-async", "--dry-run"])

    assert mock_execute.called
    assert mock_execute.call_args.kwargs.get("dry_run") is True


# ==============================================================================
# Show-prompt flag forwarding tests
# ==============================================================================


def test_plan_show_prompt_forwarded(
    monkeypatch: pytest.MonkeyPatch, mock_plan_deps: dict, tmp_path: Path
) -> None:
    """--show-prompt passes show_prompt=True to create_codeagent_command."""
    mock_spec_input = MagicMock()
    mock_spec_input.request.task_guidance = "Test task"
    monkeypatch.setattr(
        "vibe3.commands.plan.resolve_spec_plan_input",
        lambda branch, file=None: mock_spec_input,
    )
    monkeypatch.setattr(
        "vibe3.config.loader.VibeConfig.get_defaults", lambda: MagicMock()
    )

    captured_kwargs: dict = {}

    def capture_command(**kwargs: object) -> MagicMock:
        captured_kwargs.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("vibe3.commands.plan.create_codeagent_command", capture_command)
    monkeypatch.setattr(
        "vibe3.commands.plan.CodeagentExecutionService", lambda cfg: MagicMock()
    )

    spec_file = tmp_path / "spec.md"
    spec_file.write_text("# Test Spec\n")

    runner.invoke(
        plan_app,
        ["--branch", "42", "--spec", str(spec_file), "--dry-run", "--show-prompt"],
    )

    assert captured_kwargs.get("show_prompt") is True


def test_run_show_prompt_forwarded(
    monkeypatch: pytest.MonkeyPatch, mock_run_deps: dict
) -> None:
    """vibe3 run --dry-run --show-prompt forwards both flags to execute_manual_run."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    runner.invoke(
        run_app, ["--dry-run", "--show-prompt", "--no-async", "test instructions"]
    )

    assert mock_execute.called
    assert mock_execute.call_args.kwargs.get("dry_run") is True
    assert mock_execute.call_args.kwargs.get("show_prompt") is True


def test_review_show_prompt_forwarded(
    monkeypatch: pytest.MonkeyPatch, mock_review_deps: None
) -> None:
    """vibe3 review --show-prompt passes show_prompt=True to run_issue_role_sync."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.review.run_issue_role_sync", mock_execute)

    runner.invoke(review_app, ["--branch", "42", "--dry-run", "--show-prompt"])

    assert mock_execute.called
    assert mock_execute.call_args.kwargs.get("show_prompt") is True


def test_internal_manager_show_prompt_forwarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """vibe3 internal manager --show-prompt passes show_prompt=True."""
    mock_execute = MagicMock()
    monkeypatch.setattr(
        "vibe3.execution.issue_role_sync_runner.run_issue_role_sync", mock_execute
    )

    runner.invoke(
        internal_app, ["manager", "123", "--no-async", "--dry-run", "--show-prompt"]
    )

    assert mock_execute.called
    assert mock_execute.call_args.kwargs.get("show_prompt") is True


# ==============================================================================
# Config/CLI override tests
# ==============================================================================


def test_run_cli_agent_overrides_config(
    monkeypatch: pytest.MonkeyPatch, mock_run_deps: dict
) -> None:
    """--agent CLI option forwards agent to execute_manual_run."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    runner.invoke(
        run_app, ["--agent", "override-agent", "--no-async", "test instructions"]
    )

    assert mock_execute.called
    assert mock_execute.call_args.kwargs.get("agent") == "override-agent"


def test_run_cli_backend_overrides_config(
    monkeypatch: pytest.MonkeyPatch, mock_run_deps: dict
) -> None:
    """--backend CLI option is passed as cli_overrides to load_runtime_config."""
    mock_execute = MagicMock()
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", mock_execute)

    captured_overrides: dict = {}

    def capture_config(cli_overrides: dict | None = None) -> MagicMock:
        captured_overrides.update(cli_overrides or {})
        return MagicMock()

    monkeypatch.setattr("vibe3.commands.run.load_runtime_config", capture_config)

    runner.invoke(
        run_app, ["--backend", "override-backend", "--no-async", "test instructions"]
    )

    assert "run.agent_config.backend" in captured_overrides
    assert captured_overrides["run.agent_config.backend"] == "override-backend"


def test_run_no_cli_override_uses_config(
    monkeypatch: pytest.MonkeyPatch, mock_run_deps: dict
) -> None:
    """Without CLI overrides, load_runtime_config receives an empty dict."""
    monkeypatch.setattr("vibe3.commands.run.execute_manual_run", MagicMock())

    captured_overrides: dict = {}

    def capture_config(cli_overrides: dict | None = None) -> MagicMock:
        captured_overrides.update(cli_overrides or {})
        return MagicMock()

    monkeypatch.setattr("vibe3.commands.run.load_runtime_config", capture_config)

    runner.invoke(run_app, ["--no-async", "test instructions"])

    assert captured_overrides == {}
