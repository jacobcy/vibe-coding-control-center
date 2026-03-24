"""Tests for run command."""

import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app as cli_app
from vibe3.commands.run import app as run_app

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def test_run_help_shows_execute_command() -> None:
    result = runner.invoke(run_app, ["--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "execute" in stdout


def test_run_execute_help_shows_file_option() -> None:
    result = runner.invoke(run_app, ["execute", "--help"])
    stdout = strip_ansi(result.stdout)

    assert result.exit_code == 0
    assert "--file" in stdout or "-f" in stdout


def test_run_execute_requires_file_or_flow_plan() -> None:
    result = runner.invoke(run_app, ["execute"])

    assert result.exit_code != 0


def test_run_execute_file_not_found() -> None:
    result = runner.invoke(run_app, ["execute", "--file", "nonexistent.md"])

    assert result.exit_code != 0


def test_run_execute_dry_run_shows_command() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = MagicMock()
    mock_result.stdout = "Mocked execution output"

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch("vibe3.commands.run.run_review_agent", return_value=mock_result):
            result = runner.invoke(
                cli_app, ["run", "execute", "--file", "plan.md", "--dry-run"]
            )

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    # When config has backend/model, shows backend name
    assert "-> Executing plan with" in result.stdout


def test_run_execute_with_agent_override() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = MagicMock()
    mock_result.stdout = "Mocked execution output"

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch("vibe3.commands.run.run_review_agent", return_value=mock_result):
            result = runner.invoke(
                cli_app,
                [
                    "run",
                    "execute",
                    "--file",
                    "plan.md",
                    "--agent",
                    "executor-pro",
                    "--dry-run",
                ],
            )

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    # CLI --agent override shows agent name
    assert "-> Executing plan with executor-pro" in result.stdout


def test_run_execute_with_backend_override() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = MagicMock()
    mock_result.stdout = "Mocked execution output"

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch(
            "vibe3.commands.run.run_review_agent", return_value=mock_result
        ) as mock_run:
            result = runner.invoke(
                cli_app,
                [
                    "run",
                    "execute",
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
    options = mock_run.call_args.args[1]
    assert options.agent is None
    assert options.backend == "claude"
    assert options.model == "claude-3-opus"
