"""Tests for plan command."""

import re

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
