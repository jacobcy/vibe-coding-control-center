"""Tests for plan command."""

import re
from pathlib import Path
from unittest.mock import MagicMock

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

        def execute_plan(
            self,
            request,
            issue_number: int,
            branch: str,
            async_mode: bool = True,
        ):
            """Mock execute_plan for testing."""
            return MagicMock(
                success=True,
                exit_code=0,
                stdout="Plan created successfully",
                stderr="",
                handoff_file=None,
                session_id=None,
            )

    monkeypatch.setattr(
        "vibe3.commands.plan._build_plan_usecase",
        lambda config, flow_service: _StubPlanUsecase(),
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


def test_plan_issue_basic_flow(monkeypatch) -> None:
    """Test basic plan issue flow."""
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["--issue", "42"])

    assert result.exit_code == 0
    assert "Plan created successfully" in result.stdout


def test_plan_spec_msg_basic_flow(monkeypatch) -> None:
    """Test basic plan spec flow."""
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["--spec", "--msg", "Add dark mode"])

    assert result.exit_code == 0
    assert "Plan created successfully" in result.stdout


def test_plan_spec_requires_file_or_msg() -> None:
    result = runner.invoke(plan_app, ["--spec"])

    assert result.exit_code != 0


def test_plan_spec_file_not_found(monkeypatch) -> None:
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["--spec", "--file", "nonexistent.md"])

    assert result.exit_code != 0


def test_plan_task_alias_still_works(monkeypatch) -> None:
    """Test that the 'task' alias still works."""
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["task", "42"])

    assert result.exit_code == 0


def test_plan_spec_alias_still_works(monkeypatch) -> None:
    """Test that the 'spec' alias still works."""
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["spec", "--msg", "Add dark mode"])

    assert result.exit_code == 0


def test_plan_rejects_issue_and_spec_together() -> None:
    result = runner.invoke(plan_app, ["--issue", "42", "--spec"])

    assert result.exit_code != 0


def test_plan_rejects_file_without_spec() -> None:
    result = runner.invoke(plan_app, ["--file", "test.md"])

    assert result.exit_code != 0


class TestPlanContextBuilderUsesAssembler:
    """Tests for plan context builder integration."""

    def test_make_plan_context_builder_calls_body_builder(self) -> None:
        """Test that make_plan_context_builder properly integrates with assembler."""
        from vibe3.agents.plan_prompt import make_plan_context_builder
        from vibe3.config.settings import VibeConfig
        from vibe3.models.plan import PlanRequest, PlanScope

        config = VibeConfig.get_defaults()
        request = PlanRequest(scope=PlanScope.for_task(42))
        builder = make_plan_context_builder(request, config)

        # The builder should return a string when called
        context = builder()
        assert isinstance(context, str)
        assert len(context) > 0

    def test_plan_context_builder_no_longer_exports_build_plan_context(self) -> None:
        """Test that build_plan_context is no longer exported from plan_prompt."""
        import vibe3.agents.plan_prompt as plan_prompt_module

        # The old function should not be present
        assert not hasattr(plan_prompt_module, "build_plan_context")
