"""Tests for plan command."""

import re
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vibe3.commands.plan import app as plan_app

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def _patch_issue_runtime(monkeypatch) -> MagicMock:
    """Patch issue mode to use mocked run_issue_role_mode."""
    mock_runner = MagicMock()
    monkeypatch.setattr(
        "vibe3.commands.plan.run_issue_role_mode",
        mock_runner,
    )
    return mock_runner


def _patch_spec_runtime(monkeypatch) -> MagicMock:
    """Patch spec mode dependencies."""
    monkeypatch.setattr(
        "vibe3.commands.command_options.ensure_flow_for_current_branch",
        lambda: (MagicMock(), "task/test-branch"),
    )
    mock_usecase = MagicMock()
    mock_usecase_cls = MagicMock(return_value=mock_usecase)
    monkeypatch.setattr(
        "vibe3.commands.plan.PlanUsecase",
        mock_usecase_cls,
    )
    return mock_usecase


def test_plan_help_shows_options() -> None:
    result = runner.invoke(plan_app, ["--help"])
    output = strip_ansi(result.output)
    assert result.exit_code == 0
    assert "--issue" in output
    assert "--spec" in output


def test_plan_issue_exclusive_with_spec() -> None:
    result = runner.invoke(plan_app, ["--issue", "42", "--spec"])
    assert result.exit_code != 0
    assert "Error: --issue and --spec are mutually exclusive" in result.output


def test_plan_spec_requires_file_or_msg() -> None:
    result = runner.invoke(plan_app, ["--spec"])
    assert result.exit_code != 0


def test_plan_issue_basic_flow(monkeypatch) -> None:
    """Test basic plan issue flow delegates to run_issue_role_mode."""
    mock_runner = _patch_issue_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["issue", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()
    call_kwargs = mock_runner.call_args[1]
    assert call_kwargs["issue_number"] == 42


def test_plan_spec_msg_basic_flow(monkeypatch) -> None:
    """Test basic plan spec flow."""
    _patch_spec_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["spec", "--msg", "Add dark mode"])
    assert result.exit_code == 0


def test_plan_spec_file_not_found(monkeypatch) -> None:
    mock_usecase = _patch_spec_runtime(monkeypatch)
    mock_usecase.resolve_spec_plan.side_effect = FileNotFoundError("File not found")

    result = runner.invoke(plan_app, ["spec", "--file", "nonexistent.md"])
    assert result.exit_code != 0


def test_plan_issue_subcommand_still_works(monkeypatch) -> None:
    """Test that the 'issue' subcommand works."""
    mock_runner = _patch_issue_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["issue", "42"])
    assert result.exit_code == 0
    mock_runner.assert_called_once()


def test_plan_spec_subcommand_still_works(monkeypatch) -> None:
    """Test that the 'spec' subcommand works."""
    _patch_spec_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["spec", "--msg", "Add dark mode"])
    assert result.exit_code == 0
