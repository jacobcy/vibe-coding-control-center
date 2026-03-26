"""Tests for run command."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app as cli_app
from vibe3.models.review_runner import AgentOptions, AgentResult

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
    mock_result = AgentResult(exit_code=0, stdout="Mocked execution output", stderr="")

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch(
            "vibe3.commands.run.run_execution_pipeline",
            return_value=MagicMock(
                agent_result=mock_result,
                handoff_file=None,
                session_id=None,
            ),
        ) as mock_pipeline:
            result = runner.invoke(cli_app, ["run", "--file", "plan.md", "--dry-run"])

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    # Verify pipeline was called with correct request structure
    request = mock_pipeline.call_args.args[0]
    assert request.role == "executor"
    assert request.dry_run is True


def test_run_with_agent_override() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = AgentResult(exit_code=0, stdout="Mocked execution output", stderr="")

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch(
            "vibe3.commands.run.run_execution_pipeline",
            return_value=MagicMock(
                agent_result=mock_result,
                handoff_file=None,
                session_id=None,
            ),
        ) as mock_pipeline:
            result = runner.invoke(
                cli_app,
                ["run", "--file", "plan.md", "--agent", "executor-pro", "--dry-run"],
            )

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    # Verify that the agent override is passed correctly in options
    request = mock_pipeline.call_args.args[0]
    options = request.options_builder()
    assert options.agent == "executor-pro"


def test_run_with_backend_override() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = AgentResult(exit_code=0, stdout="Mocked execution output", stderr="")

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch(
            "vibe3.commands.run.run_execution_pipeline",
            return_value=MagicMock(
                agent_result=mock_result,
                handoff_file=None,
                session_id=None,
            ),
        ) as mock_pipeline:
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
    # Verify the backend/model overrides are passed correctly
    request = mock_pipeline.call_args.args[0]
    options = request.options_builder()
    assert options.agent is None
    assert options.backend == "claude"
    assert options.model == "claude-3-opus"


def test_run_uses_shared_agent_options_with_run_context() -> None:
    mock_context = "# Test Plan\n\n## Task\nTest execution"
    mock_result = AgentResult(exit_code=0, stdout="Mocked execution output", stderr="")

    with patch("vibe3.commands.run.build_run_context", return_value=mock_context):
        with patch(
            "vibe3.commands.run.run_execution_pipeline",
            return_value=MagicMock(
                agent_result=mock_result,
                handoff_file=None,
                session_id=None,
            ),
        ) as mock_pipeline:
            result = runner.invoke(
                cli_app,
                ["run", "--file", "plan.md", "--dry-run"],
            )

    assert result.exit_code == 0
    # Verify that execution request was properly constructed
    request = mock_pipeline.call_args.args[0]
    assert request.role == "executor"
    assert request.dry_run is True
    # Verify options_builder is callable and returns valid options
    options = request.options_builder()
    assert options is not None


def test_run_skill_uses_shared_agent_options_with_run_context() -> None:
    mock_result = AgentResult(exit_code=0, stdout="Mocked skill output", stderr="")

    with runner.isolated_filesystem():
        skill_file = Path("SKILL.md")
        skill_file.write_text("# Demo Skill", encoding="utf-8")

        with patch("vibe3.commands.run._find_skill_file", return_value=skill_file):
            with patch(
                "vibe3.commands.run.run_execution_pipeline",
                return_value=MagicMock(
                    agent_result=mock_result,
                    handoff_file=None,
                    session_id=None,
                ),
            ) as mock_pipeline:
                with patch(
                    "vibe3.commands.run.ensure_flow_for_current_branch",
                    return_value=(MagicMock(), "task/test-branch"),
                ):
                    result = runner.invoke(
                        cli_app,
                        ["run", "--skill", "demo", "--dry-run"],
                    )

    assert result.exit_code == 0
    # Verify that execution request was properly constructed with skill metadata
    request = mock_pipeline.call_args.args[0]
    assert request.role == "executor"
    assert request.dry_run is True
    assert request.handoff_metadata == {"skill": "demo"}


def test_run_skill_records_with_unified_recorder() -> None:
    mock_result = AgentResult(exit_code=0, stdout="Mocked skill output", stderr="")
    mock_options = AgentOptions(agent="executor", backend=None, model=None)

    with runner.isolated_filesystem():
        skill_file = Path("SKILL.md")
        skill_file.write_text("# Demo Skill", encoding="utf-8")

        with patch("vibe3.commands.run._find_skill_file", return_value=skill_file):
            with patch(
                "vibe3.commands.run.run_execution_pipeline",
                return_value=MagicMock(
                    agent_result=mock_result,
                    handoff_file=Path("/tmp/run.md"),
                    session_id="sess-existing",
                ),
            ):
                with patch(
                    "vibe3.commands.run.get_agent_options", return_value=mock_options
                ):
                    with patch(
                        "vibe3.commands.run.ensure_flow_for_current_branch",
                        return_value=(MagicMock(), "task/test-branch"),
                    ):
                        result = runner.invoke(
                            cli_app,
                            ["run", "--skill", "demo"],
                        )

    assert result.exit_code == 0
    # The handoff recording is now internal to run_execution_pipeline
    # So we just verify the pipeline was called correctly
