"""Tests for plan command."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

from vibe3.agents.plan_agent import PlanSpecInput, PlanTaskInput
from vibe3.cli import app as cli_app
from vibe3.commands.plan import app as plan_app
from vibe3.models.plan import PlanRequest, PlanScope

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def _patch_fast_plan_runtime(monkeypatch) -> None:
    """Stub plan command runtime for CLI surface tests."""
    monkeypatch.setattr(
        "vibe3.commands.plan.ensure_flow_for_current_branch",
        lambda: (MagicMock(), "task/demo"),
    )

    class _StubPlanUsecase:
        def resolve_task_plan(self, branch: str, issue_number: int | None = None):
            resolved_issue = issue_number or 42
            return PlanTaskInput(
                issue_number=resolved_issue,
                branch=branch,
                request=PlanRequest(scope=PlanScope.for_task(resolved_issue)),
            )

        def resolve_spec_plan(
            self,
            branch: str,
            file: Path | None = None,
            msg: str | None = None,
        ):
            if file is not None and not file.exists():
                raise FileNotFoundError(f"File not found: {file}")
            description = file.read_text(encoding="utf-8") if file else (msg or "")
            return PlanSpecInput(
                branch=branch,
                request=PlanRequest(scope=PlanScope.for_spec(description)),
                description=description,
                spec_path=str(file.resolve()) if file else None,
            )

        def bind_spec(self, branch: str, spec_path: str) -> None:
            return None

    monkeypatch.setattr(
        "vibe3.commands.plan._build_plan_usecase",
        lambda config, flow_service: _StubPlanUsecase(),
    )

    def _fake_execute(self, command, async_mode=False):
        parts = ["codeagent-wrapper", "--role", command.role]
        if command.dry_run:
            parts.append("--dry-run")
        resolved_agent = command.agent
        resolved_backend = command.backend
        resolved_model = command.model
        if command.config and getattr(command.config, "plan", None):
            agent_cfg = command.config.plan.agent_config
            resolved_agent = resolved_agent or agent_cfg.agent
            resolved_backend = resolved_backend or agent_cfg.backend
            resolved_model = resolved_model or agent_cfg.model
        if resolved_agent:
            parts.extend(["--agent", resolved_agent])
        if resolved_backend:
            parts.extend(["--backend", resolved_backend])
        if resolved_model:
            parts.extend(["--model", resolved_model])
        if command.worktree:
            parts.append("--worktree")
        typer.echo(" ".join(parts))
        return MagicMock(
            success=True,
            exit_code=0,
            stdout=" ".join(parts),
            stderr="",
            handoff_file=None,
            session_id=None,
        )

    monkeypatch.setattr(
        "vibe3.agents.runner.CodeagentExecutionService.execute",
        _fake_execute,
    )


def test_plan_help_shows_subcommands() -> None:
    result = runner.invoke(plan_app, ["--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--issue" in stdout
    assert "--spec" in stdout


def test_main_cli_registers_plan_command() -> None:
    result = runner.invoke(cli_app, ["plan", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--issue" in stdout
    assert "--spec" in stdout


def test_plan_issue_option_shows_in_help() -> None:
    result = runner.invoke(plan_app, ["--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--issue" in stdout


def test_plan_spec_help_shows_options() -> None:
    result = runner.invoke(plan_app, ["--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--file" in stdout or "-f" in stdout
    assert "--msg" in stdout
    assert "--spec" in stdout
    assert "--message" not in stdout


def test_plan_issue_dry_run_shows_command(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["--issue", "42", "--dry-run"])

    assert result.exit_code == 0
    assert "codeagent-wrapper" in result.stdout
    # When config has backend/model, it uses --backend --model instead of --agent
    assert "--backend" in result.stdout or "--agent" in result.stdout


def test_plan_issue_with_agent_override(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(
        plan_app, ["--issue", "42", "--agent", "planner-pro", "--dry-run"]
    )

    assert result.exit_code == 0
    # CLI --agent override takes precedence
    assert "--agent planner-pro" in result.stdout


def test_plan_spec_msg_dry_run(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["--spec", "--msg", "Add dark mode", "--dry-run"])

    assert result.exit_code == 0
    assert "codeagent-wrapper" in result.stdout


def test_plan_spec_requires_file_or_msg() -> None:
    result = runner.invoke(plan_app, ["--spec"])

    assert result.exit_code != 0


def test_plan_spec_file_not_found(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["--spec", "--file", "nonexistent.md"])

    assert result.exit_code != 0


@patch("vibe3.services.spec_ref_service.SpecRefService._fetch_issue_data")
@patch("vibe3.commands.plan.CodeagentExecutionService.execute")
@patch("vibe3.commands.plan.FlowService")
@patch("vibe3.commands.plan.ensure_flow_for_current_branch")
def test_plan_issue_includes_issue_and_spec_context(
    mock_ensure, mock_flow_service_cls, mock_execute, mock_fetch_issue
) -> None:
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(
        task_issue_number=42,
        spec_ref="#55:Spec title",
    )
    mock_ensure.return_value = (flow_service, "task/demo")

    issue_client = MagicMock()
    issue_client.view_issue.side_effect = [
        {"number": 42, "title": "Task title", "body": "Task body"},
        {"number": 55, "title": "Spec title", "body": "Spec body"},
    ]
    mock_fetch_issue.return_value = {
        "number": 55,
        "title": "Spec title",
        "body": "Spec body",
    }

    with patch("vibe3.agents.plan_agent.GitHubClient", return_value=issue_client):
        mock_execute.return_value = MagicMock(success=True)
        result = runner.invoke(plan_app, ["--issue", "42"])

    assert result.exit_code == 0
    command = mock_execute.call_args.args[0]
    context = command.context_builder()
    assert "Task title" in context
    assert "Task body" in context
    assert "Spec title" in context
    assert "Spec body" in context


def test_plan_task_alias_still_works(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["task", "42", "--dry-run"])

    assert result.exit_code == 0


def test_plan_success_transitions_issue_to_handoff(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)
    with patch("vibe3.commands.plan._svc_confirm_handoff") as mock_handoff:
        mock_handoff.return_value = "advanced"
        result = runner.invoke(plan_app, ["--issue", "42", "--sync"])

    assert result.exit_code == 0
    mock_handoff.assert_called_once_with(
        issue_number=42,
        actor="agent:plan",
    )


def test_plan_failure_fails_issue_and_comments(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)

    def _failed_execute(self, command, async_mode=False):
        return MagicMock(success=False, stderr="planner failed")

    monkeypatch.setattr(
        "vibe3.agents.runner.CodeagentExecutionService.execute",
        _failed_execute,
    )

    with patch("vibe3.commands.plan._svc_fail_planner") as mock_fail:
        result = runner.invoke(plan_app, ["--issue", "42", "--sync"])

    assert result.exit_code != 0
    mock_fail.assert_called_once_with(
        issue_number=42,
        reason="planner failed",
        actor="agent:plan",
    )
    assert "state/failed" in result.stderr


def test_plan_timeout_exception_fails_issue_and_comments(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)

    def _raise_timeout(self, command, async_mode=False):
        raise RuntimeError("codeagent-wrapper timed out after 600s")

    monkeypatch.setattr(
        "vibe3.agents.runner.CodeagentExecutionService.execute",
        _raise_timeout,
    )

    with patch("vibe3.commands.plan._svc_fail_planner") as mock_fail:
        result = runner.invoke(plan_app, ["--issue", "42", "--sync"])

    assert result.exit_code != 0
    mock_fail.assert_called_once_with(
        issue_number=42,
        reason="codeagent-wrapper timed out after 600s",
        actor="agent:plan",
    )
    assert "state/failed" in result.stderr


def test_plan_spec_alias_still_works(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["spec", "--msg", "Add dark mode", "--dry-run"])

    assert result.exit_code == 0
    assert "codeagent-wrapper" in result.stdout


def test_plan_rejects_issue_and_spec_together() -> None:
    result = runner.invoke(plan_app, ["--issue", "42", "--spec"])

    assert result.exit_code != 0
    assert "--issue and --spec are mutually exclusive" in result.stderr


def test_plan_rejects_file_without_spec() -> None:
    result = runner.invoke(plan_app, ["--file", "demo.md"])

    assert result.exit_code != 0
    assert "--file/--msg require --spec" in result.stderr


class TestPlanContextBuilderUsesAssembler:
    """Assert plan command context builders go through PromptAssembler."""

    def test_make_plan_context_builder_calls_body_builder(self) -> None:
        """make_plan_context_builder should invoke build_plan_prompt_body."""
        from unittest.mock import MagicMock, patch

        from vibe3.agents.plan_prompt import make_plan_context_builder
        from vibe3.config.settings import VibeConfig

        config = VibeConfig.get_defaults()
        request = MagicMock()
        with patch(
            "vibe3.agents.plan_prompt.build_plan_prompt_body",
            return_value="assembled plan body",
        ):
            cb = make_plan_context_builder(request, config)
            text = cb()

        assert text == "assembled plan body"
        assert cb.last_result is not None
        assert cb.last_result.recipe_key == "plan.default"

    def test_plan_context_builder_no_longer_exports_build_plan_context(self) -> None:
        """build_plan_context (old name) must not exist in plan_context_builder."""
        import vibe3.agents.plan_prompt as mod

        assert not hasattr(
            mod, "build_plan_context"
        ), "build_plan_context should be deleted; use build_plan_prompt_body"
