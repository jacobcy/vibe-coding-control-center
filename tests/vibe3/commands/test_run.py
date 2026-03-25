"""Tests for run command."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app as cli_app
from vibe3.models.agent_execution import AgentExecutionOutcome
from vibe3.models.review_runner import ReviewAgentOptions

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def test_run_help_shows_direct_instruction_usage() -> None:
    result = runner.invoke(cli_app, ["run", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "[INSTRUCTIONS]" in stdout
    assert "COMMAND [ARGS]" not in stdout
    assert re.search(r"^\s+execute\s", stdout, re.MULTILINE) is None
    assert "--message" not in stdout


def test_run_direct_help_shows_file_option() -> None:
    result = runner.invoke(cli_app, ["run", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--file" in stdout or "-f" in stdout


def test_run_file_not_found() -> None:
    result = runner.invoke(cli_app, ["run", "--file", "nonexistent.md"])

    assert result.exit_code != 0


def test_run_dry_run_shows_command() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = MagicMock(stdout="Mocked execution output")
    mock_outcome = AgentExecutionOutcome(result=mock_result, effective_session_id=None)

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch("vibe3.commands.run.execute_agent", return_value=mock_outcome):
            result = runner.invoke(cli_app, ["run", "--file", "plan.md", "--dry-run"])

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    # When config has backend/model, shows backend name
    assert "-> Executing plan with" in result.stdout


def test_run_with_agent_override() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = MagicMock(stdout="Mocked execution output")
    mock_outcome = AgentExecutionOutcome(result=mock_result, effective_session_id=None)

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch("vibe3.commands.run.execute_agent", return_value=mock_outcome):
            result = runner.invoke(
                cli_app,
                ["run", "--file", "plan.md", "--agent", "executor-pro", "--dry-run"],
            )

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    # CLI --agent override shows agent name
    assert "-> Executing plan with executor-pro" in result.stdout


def test_run_with_backend_override() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = MagicMock(stdout="Mocked execution output")
    mock_outcome = AgentExecutionOutcome(result=mock_result, effective_session_id=None)

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch(
            "vibe3.commands.run.execute_agent", return_value=mock_outcome
        ) as mock_exec:
            result = runner.invoke(
                cli_app,
                [
                    "run",
                    "--file",
                    "plan.md",
                    "--backend",
                    "claude",
                    "--model",
                    "claude-3-opus",
                    "--dry-run",
                ],
            )

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    assert "-> Executing plan with claude" in result.stdout
    request = mock_exec.call_args.args[0]
    options = request.options
    assert options.agent is None
    assert options.backend == "claude"
    assert options.model == "claude-3-opus"


def test_run_uses_shared_agent_options_with_run_context() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = MagicMock(stdout="Mocked execution output")
    mock_outcome = AgentExecutionOutcome(result=mock_result, effective_session_id=None)
    mock_options = ReviewAgentOptions(agent="executor", backend=None, model=None)

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch("vibe3.commands.run.execute_agent", return_value=mock_outcome):
            with patch(
                "vibe3.commands.run.get_agent_options", return_value=mock_options
            ) as mock_get_options:
                result = runner.invoke(
                    cli_app,
                    ["run", "--file", "plan.md", "--dry-run"],
                )

    assert result.exit_code == 0
    mock_get_options.assert_called_once()
    args, kwargs = mock_get_options.call_args
    assert len(args) == 4
    assert args[1:] == (None, None, None)
    assert kwargs["section"] == "run"
    assert kwargs["default_agent"] == "executor"


def test_run_skill_uses_shared_agent_options_with_run_context() -> None:
    mock_result = MagicMock(stdout="Mocked skill output")
    mock_outcome = AgentExecutionOutcome(result=mock_result, effective_session_id=None)
    mock_options = ReviewAgentOptions(agent="executor", backend=None, model=None)

    with runner.isolated_filesystem():
        skill_file = Path("SKILL.md")
        skill_file.write_text("# Demo Skill", encoding="utf-8")

        with patch("vibe3.commands.run._find_skill_file", return_value=skill_file):
            with patch("vibe3.commands.run.execute_agent", return_value=mock_outcome):
                with patch(
                    "vibe3.commands.run.get_agent_options", return_value=mock_options
                ) as mock_get_options:
                    with patch("vibe3.commands.run.GitClient") as mock_git_class:
                        mock_git = MagicMock()
                        mock_git.get_current_branch.return_value = "task/test-branch"
                        mock_git_class.return_value = mock_git

                        with patch("vibe3.commands.run.FlowService") as mock_flow_class:
                            mock_flow_service = MagicMock()
                            mock_flow_service.ensure_flow_for_branch.return_value = None
                            mock_flow_class.return_value = mock_flow_service

                            result = runner.invoke(
                                cli_app,
                                ["run", "--skill", "demo", "--dry-run"],
                            )

    assert result.exit_code == 0
    mock_get_options.assert_called_once()
    args, kwargs = mock_get_options.call_args
    assert len(args) == 4
    assert args[1:] == (None, None, None)
    assert kwargs["section"] == "run"
    assert kwargs["default_agent"] == "executor"
