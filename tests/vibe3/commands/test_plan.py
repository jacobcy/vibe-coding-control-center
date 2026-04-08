"""Tests for plan command."""

from unittest.mock import MagicMock

from typer.testing import CliRunner

from vibe3.commands.plan import app as plan_app

runner = CliRunner()


def _patch_fast_plan_runtime(monkeypatch) -> MagicMock:
    monkeypatch.setattr(
        "vibe3.commands.command_options.ensure_flow_for_current_branch",
        lambda: (MagicMock(), "task/test-branch"),
    )
    # PlanUsecase signature might have changed, but command uses _build_plan_usecase
    mock_usecase = MagicMock()
    # Handle both new and old signature if necessary, but here we patch the builder
    monkeypatch.setattr(
        "vibe3.commands.plan._build_plan_usecase",
        lambda flow_service=None: mock_usecase,
    )
    return mock_usecase


def test_plan_help_shows_options() -> None:
    result = runner.invoke(plan_app, ["--help"])
    assert result.exit_code == 0
    assert "--issue" in result.output
    assert "--spec" in result.output


def test_plan_issue_exclusive_with_spec() -> None:
    result = runner.invoke(plan_app, ["--issue", "42", "--spec"])
    assert result.exit_code != 0
    assert "Error: --issue and --spec are mutually exclusive" in result.output


def test_plan_spec_requires_file_or_msg() -> None:
    # Typer raises SystemExit(1) for resolve_spec_plan validation error in current impl
    result = runner.invoke(plan_app, ["--spec"])
    assert result.exit_code != 0


def test_plan_issue_basic_flow(monkeypatch) -> None:
    """Test basic plan issue flow."""
    _patch_fast_plan_runtime(monkeypatch)
    # Use 'issue' subcommand explicitly to be safe
    result = runner.invoke(plan_app, ["issue", "42"])
    assert result.exit_code == 0


def test_plan_spec_msg_basic_flow(monkeypatch) -> None:
    """Test basic plan spec flow."""
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["spec", "--msg", "Add dark mode"])
    assert result.exit_code == 0


def test_plan_spec_file_not_found(monkeypatch) -> None:
    mock_usecase = _patch_fast_plan_runtime(monkeypatch)
    # Make resolve_spec_plan raise the error to simulate missing file
    mock_usecase.resolve_spec_plan.side_effect = FileNotFoundError("File not found")

    result = runner.invoke(plan_app, ["spec", "--file", "nonexistent.md"])
    assert result.exit_code != 0


def test_plan_issue_subcommand_still_works(monkeypatch) -> None:
    """Test that the 'issue' subcommand works."""
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["issue", "42"])
    assert result.exit_code == 0


def test_plan_spec_subcommand_still_works(monkeypatch) -> None:
    """Test that the 'spec' subcommand works."""
    _patch_fast_plan_runtime(monkeypatch)
    result = runner.invoke(plan_app, ["spec", "--msg", "Add dark mode"])
    assert result.exit_code == 0
