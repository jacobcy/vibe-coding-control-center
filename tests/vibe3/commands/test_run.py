"""Tests for run command."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.agents.run_agent import RunUsecase
from vibe3.cli import app as cli_app
from vibe3.config.settings import VibeConfig
from vibe3.domain.events import (
    IssueFailed,
    IssueStateChanged,
)

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def _patch_fast_run_runtime(monkeypatch) -> None:
    monkeypatch.setattr(
        "vibe3.commands.command_options.ensure_flow_for_current_branch",
        lambda: (MagicMock(), "task/test-branch"),
    )
    from vibe3.config.settings import AgentConfig, RunConfig

    cfg = VibeConfig(
        run=RunConfig(agent_config=AgentConfig(agent="executor")),
    )
    monkeypatch.setattr(
        VibeConfig,
        "get_defaults",
        classmethod(lambda cls: cfg),
    )


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
    with patch(
        "vibe3.commands.command_options.ensure_flow_for_current_branch",
        return_value=(MagicMock(), "task/test-branch"),
    ):
        with patch(
            "vibe3.config.settings.VibeConfig.get_defaults",
            return_value=VibeConfig(),
        ):
            with patch(
                "vibe3.commands.run.CodeagentExecutionService.execute_sync",
                return_value=MagicMock(success=True),
            ) as mock_execute:
                result = runner.invoke(cli_app, ["run", "--plan", "nonexistent.md"])

    assert result.exit_code != 0
    assert "Plan file not found: nonexistent.md" in strip_ansi(result.output)
    mock_execute.assert_not_called()


def test_find_skill_file_prefers_current_worktree(tmp_path, monkeypatch) -> None:
    worktree_skill = tmp_path / "skills" / "demo" / "SKILL.md"
    worktree_skill.parent.mkdir(parents=True)
    worktree_skill.write_text("# Worktree Skill", encoding="utf-8")

    repo_root = tmp_path / "repo-root"
    repo_skill = repo_root / "skills" / "demo" / "SKILL.md"
    repo_skill.parent.mkdir(parents=True)
    repo_skill.write_text("# Main Repo Skill", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    flow_service = MagicMock()
    flow_service.get_git_common_dir.return_value = str(repo_root / ".git")

    assert (
        RunUsecase.find_skill_file("demo", flow_service=flow_service) == worktree_skill
    )


def test_run_dry_run_shows_command(monkeypatch) -> None:
    _patch_fast_run_runtime(monkeypatch)
    with patch("vibe3.commands.run._ensure_plan_file_exists"):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute",
            return_value=MagicMock(success=True),
        ) as mock_execute:
            result = runner.invoke(cli_app, ["run", "--plan", "plan.md", "--dry-run"])

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    command = mock_execute.call_args.args[0]
    assert command.role == "executor"
    assert command.dry_run is True


def test_run_with_agent_override(monkeypatch) -> None:
    _patch_fast_run_runtime(monkeypatch)
    with patch("vibe3.commands.run._ensure_plan_file_exists"):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute",
            return_value=MagicMock(success=True),
        ) as mock_execute:
            result = runner.invoke(
                cli_app,
                [
                    "run",
                    "--plan",
                    "plan.md",
                    "--agent",
                    "executor-pro",
                    "--dry-run",
                ],
            )

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    command = mock_execute.call_args.args[0]
    assert command.agent == "executor-pro"


def test_run_with_backend_override(monkeypatch) -> None:
    _patch_fast_run_runtime(monkeypatch)
    with patch("vibe3.commands.run._ensure_plan_file_exists"):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute",
            return_value=MagicMock(success=True),
        ) as mock_execute:
            result = runner.invoke(
                cli_app,
                [
                    "run",
                    "--plan",
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
    command = mock_execute.call_args.args[0]
    assert command.agent is None
    assert command.backend == "claude"
    assert command.model == "claude-3-opus"


def test_run_uses_shared_agent_options_with_run_context(monkeypatch) -> None:
    _patch_fast_run_runtime(monkeypatch)
    with patch("vibe3.commands.run._ensure_plan_file_exists"):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute",
            return_value=MagicMock(success=True),
        ) as mock_execute:
            result = runner.invoke(
                cli_app,
                ["run", "--plan", "plan.md", "--dry-run"],
            )

    assert result.exit_code == 0
    command = mock_execute.call_args.args[0]
    assert command.role == "executor"
    assert command.dry_run is True
    assert command.handoff_metadata == {"plan_ref": "plan.md"}
    assert callable(command.context_builder)


def test_run_skill_uses_shared_agent_options_with_run_context() -> None:
    with runner.isolated_filesystem():
        skill_file = Path("SKILL.md")
        skill_file.write_text("# Demo Skill", encoding="utf-8")

        with patch("vibe3.commands.run._find_skill_file", return_value=skill_file):
            with patch(
                "vibe3.commands.run.CodeagentExecutionService.execute",
                return_value=MagicMock(success=True),
            ) as mock_execute:
                with patch(
                    "vibe3.commands.command_options.ensure_flow_for_current_branch",
                    return_value=(MagicMock(), "task/test-branch"),
                ):
                    with patch(
                        "vibe3.config.settings.VibeConfig.get_defaults",
                        return_value=VibeConfig(),
                    ):
                        result = runner.invoke(
                            cli_app,
                            ["run", "--skill", "demo", "--dry-run"],
                        )

    assert result.exit_code == 0
    command = mock_execute.call_args.args[0]
    assert command.role == "executor"
    assert command.dry_run is True
    assert command.handoff_metadata == {"skill": "demo"}
    assert command.context_builder() == "# Demo Skill"


def test_run_skill_records_with_unified_recorder() -> None:
    with runner.isolated_filesystem():
        skill_file = Path("SKILL.md")
        skill_file.write_text("# Demo Skill", encoding="utf-8")

        with patch("vibe3.commands.run._find_skill_file", return_value=skill_file):
            with patch(
                "vibe3.commands.run.CodeagentExecutionService.execute",
                return_value=MagicMock(success=True),
            ) as mock_execute:
                with patch(
                    "vibe3.commands.command_options.ensure_flow_for_current_branch",
                    return_value=(MagicMock(), "task/test-branch"),
                ):
                    with patch(
                        "vibe3.config.settings.VibeConfig.get_defaults",
                        return_value=VibeConfig(),
                    ):
                        result = runner.invoke(
                            cli_app,
                            ["run", "--skill", "demo"],
                        )

    assert result.exit_code == 0
    command = mock_execute.call_args.args[0]
    assert command.task == "Execute skill: demo"


def test_run_success_invokes_callbacks_via_event_driven_architecture(
    monkeypatch,
) -> None:
    _patch_fast_run_runtime(monkeypatch)
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(task_issue_number=42)
    with (
        patch(
            "vibe3.commands.command_options.ensure_flow_for_current_branch",
            return_value=(flow_service, "task/test-branch"),
        ),
        patch("vibe3.commands.run._ensure_plan_file_exists"),
        patch(
            "vibe3.commands.run.CodeagentExecutionService.execute_with_callbacks",
        ) as mock_exec_with_callbacks,
        patch.object(RunUsecase, "transition_issue", return_value=42),
        patch.object(
            RunUsecase,
            "resolve_run_mode",
            return_value=MagicMock(mode="plan", plan_file="plan.md"),
        ),
        patch("vibe3.domain.publisher.publish") as mock_publish,
    ):
        result = runner.invoke(cli_app, ["run", "--plan", "plan.md", "--no-async"])

    assert result.exit_code == 0
    # verify execute_with_callbacks was called
    mock_exec_with_callbacks.assert_called_once()

    # Manually trigger success callback to verify event publishing
    from vibe3.agents.models import CodeagentResult

    on_success = mock_exec_with_callbacks.call_args.kwargs["on_success"]
    # Create result with handoff_file
    result_with_handoff = CodeagentResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        handoff_file=Path("/tmp/handoff.md"),
        session_id=None,
        pid=None,
        tmux_session=None,
        log_path=None,
    )
    on_success(result_with_handoff)

    # Should publish only IssueStateChanged (has handoff_file)
    assert mock_publish.call_count == 1
    event = mock_publish.call_args[0][0]
    assert isinstance(event, IssueStateChanged)


def test_run_failure_invokes_failure_callback(monkeypatch) -> None:
    _patch_fast_run_runtime(monkeypatch)
    flow_service = MagicMock()
    flow_service.get_flow_status.return_value = MagicMock(task_issue_number=42)
    with (
        patch(
            "vibe3.commands.command_options.ensure_flow_for_current_branch",
            return_value=(flow_service, "task/test-branch"),
        ),
        patch("vibe3.commands.run._ensure_plan_file_exists"),
        patch(
            "vibe3.commands.run.CodeagentExecutionService.execute_with_callbacks",
        ) as mock_exec_with_callbacks,
        patch.object(RunUsecase, "transition_issue", return_value=42),
        patch.object(
            RunUsecase,
            "resolve_run_mode",
            return_value=MagicMock(mode="plan", plan_file="plan.md"),
        ),
        patch("vibe3.domain.publisher.publish") as mock_publish,
    ):
        result = runner.invoke(cli_app, ["run", "--plan", "plan.md", "--no-async"])

    assert result.exit_code == 0
    mock_exec_with_callbacks.assert_called_once()

    # Manually trigger failure callback
    on_failure = mock_exec_with_callbacks.call_args.kwargs["on_failure"]
    on_failure(Exception("executor failed"))

    mock_publish.assert_called_once()
    event = mock_publish.call_args[0][0]
    assert isinstance(event, IssueFailed)
    assert event.reason == "executor failed"
