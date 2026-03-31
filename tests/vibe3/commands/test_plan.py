"""Tests for plan command."""

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app as cli_app
from vibe3.commands.plan import app as plan_app

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def test_plan_help_shows_subcommands() -> None:
    result = runner.invoke(plan_app, ["--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "task" in stdout
    assert "spec" in stdout


def test_main_cli_registers_plan_command() -> None:
    result = runner.invoke(cli_app, ["plan", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "task" in stdout
    assert "spec" in stdout


def test_plan_task_help_shows_issue_argument() -> None:
    result = runner.invoke(plan_app, ["task", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "ISSUE" in stdout or "issue" in stdout.lower()


def test_plan_spec_help_shows_options() -> None:
    result = runner.invoke(plan_app, ["spec", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--file" in stdout or "-f" in stdout
    assert "--msg" in stdout
    assert "--message" not in stdout


def test_plan_task_dry_run_shows_command() -> None:
    result = runner.invoke(plan_app, ["task", "42", "--dry-run"])

    assert result.exit_code == 0
    assert "codeagent-wrapper" in result.stdout
    # When config has backend/model, it uses --backend --model instead of --agent
    assert "--backend" in result.stdout or "--agent" in result.stdout


def test_plan_task_with_agent_override() -> None:
    result = runner.invoke(
        plan_app, ["task", "42", "--agent", "planner-pro", "--dry-run"]
    )

    assert result.exit_code == 0
    # CLI --agent override takes precedence
    assert "--agent planner-pro" in result.stdout


def test_plan_task_with_instructions() -> None:
    result = runner.invoke(plan_app, ["task", "42", "Focus on security", "--dry-run"])

    assert result.exit_code == 0
    assert "Focus on security" in result.stdout


def test_plan_spec_msg_dry_run() -> None:
    result = runner.invoke(plan_app, ["spec", "--msg", "Add dark mode", "--dry-run"])

    assert result.exit_code == 0
    assert "codeagent-wrapper" in result.stdout


def test_plan_spec_requires_file_or_msg() -> None:
    result = runner.invoke(plan_app, ["spec"])

    assert result.exit_code != 0


def test_plan_spec_file_not_found() -> None:
    result = runner.invoke(plan_app, ["spec", "--file", "nonexistent.md"])

    assert result.exit_code != 0


@patch("vibe3.services.spec_ref_service.SpecRefService._fetch_issue_data")
@patch("vibe3.commands.plan.CodeagentExecutionService.execute_sync")
@patch("vibe3.commands.plan.FlowService")
@patch("vibe3.commands.plan.ensure_flow_for_current_branch")
def test_plan_task_includes_issue_and_spec_context(
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

    with patch("vibe3.commands.plan.GitHubClient", return_value=issue_client):
        mock_execute.return_value = MagicMock(success=True)
        result = runner.invoke(plan_app, ["task"])

    assert result.exit_code == 0
    command = mock_execute.call_args.args[0]
    context = command.context_builder()
    assert "Task title" in context
    assert "Task body" in context
    assert "Spec title" in context
    assert "Spec body" in context


class TestPlanContextBuilderUsesAssembler:
    """Assert plan command context builders go through PromptAssembler."""

    def test_make_plan_context_builder_calls_body_builder(self) -> None:
        """make_plan_context_builder should invoke build_plan_prompt_body."""
        from unittest.mock import MagicMock, patch

        from vibe3.config.settings import VibeConfig
        from vibe3.services.plan_context_builder import make_plan_context_builder

        config = VibeConfig.get_defaults()
        request = MagicMock()
        with patch(
            "vibe3.services.plan_context_builder.build_plan_prompt_body",
            return_value="assembled plan body",
        ):
            cb = make_plan_context_builder(request, config)
            text = cb()

        assert text == "assembled plan body"
        assert cb.last_result is not None
        assert cb.last_result.recipe_key == "plan.default"

    def test_plan_context_builder_no_longer_exports_build_plan_context(self) -> None:
        """build_plan_context (old name) must not exist in plan_context_builder."""
        import vibe3.services.plan_context_builder as mod

        assert not hasattr(
            mod, "build_plan_context"
        ), "build_plan_context should be deleted; use build_plan_prompt_body"
