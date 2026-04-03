"""Tests for run command."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.agents.run_agent import RunUsecase
from vibe3.cli import app as cli_app

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
    with patch(
        "vibe3.commands.run.ensure_flow_for_current_branch",
        return_value=(MagicMock(), "task/test-branch"),
    ):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute_sync",
            return_value=MagicMock(success=True),
        ) as mock_execute:
            result = runner.invoke(cli_app, ["run", "--file", "nonexistent.md"])

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


def test_run_dry_run_shows_command() -> None:
    with patch("vibe3.commands.run._ensure_plan_file_exists"):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute_sync",
            return_value=MagicMock(success=True),
        ) as mock_execute:
            result = runner.invoke(cli_app, ["run", "--file", "plan.md", "--dry-run"])

    assert result.exit_code == 0
    assert "-> Execute: plan.md" in result.stdout
    command = mock_execute.call_args.args[0]
    assert command.role == "executor"
    assert command.dry_run is True


def test_run_with_agent_override() -> None:
    with patch("vibe3.commands.run._ensure_plan_file_exists"):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute_sync",
            return_value=MagicMock(success=True),
        ) as mock_execute:
            result = runner.invoke(
                cli_app,
                [
                    "run",
                    "--file",
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


def test_run_with_backend_override() -> None:
    with patch("vibe3.commands.run._ensure_plan_file_exists"):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute_sync",
            return_value=MagicMock(success=True),
        ) as mock_execute:
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
    command = mock_execute.call_args.args[0]
    assert command.agent is None
    assert command.backend == "claude"
    assert command.model == "claude-3-opus"


def test_run_uses_shared_agent_options_with_run_context() -> None:
    with patch("vibe3.commands.run._ensure_plan_file_exists"):
        with patch(
            "vibe3.commands.run.CodeagentExecutionService.execute_sync",
            return_value=MagicMock(success=True),
        ) as mock_execute:
            result = runner.invoke(
                cli_app,
                ["run", "--file", "plan.md", "--dry-run"],
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
                    "vibe3.commands.run.ensure_flow_for_current_branch",
                    return_value=(MagicMock(), "task/test-branch"),
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
                    "vibe3.commands.run.ensure_flow_for_current_branch",
                    return_value=(MagicMock(), "task/test-branch"),
                ):
                    result = runner.invoke(
                        cli_app,
                        ["run", "--skill", "demo"],
                    )

    assert result.exit_code == 0
    command = mock_execute.call_args.args[0]
    assert command.task == "Execute skill: demo"


class TestRunContextBuilderUsesAssembler:
    """Assert run command context builders go through PromptAssembler."""

    def test_make_skill_context_builder_returns_skill_content(self) -> None:
        """make_skill_context_builder should return skill text via assembler."""
        from vibe3.agents.run_prompt import make_skill_context_builder

        cb = make_skill_context_builder("# Demo Skill")
        text = cb()
        assert text == "# Demo Skill"

    def test_skill_context_builder_exposes_render_result(self) -> None:
        """Context builder should expose last_result after being called."""
        from vibe3.agents.run_prompt import make_skill_context_builder

        cb = make_skill_context_builder("# My Skill")
        cb()
        assert hasattr(cb, "last_result")
        assert cb.last_result is not None
        assert cb.last_result.recipe_key == "run.skill"

    def test_make_run_context_builder_calls_body_builder(self, tmp_path) -> None:
        """make_run_context_builder provider should invoke build_run_prompt_body."""
        from unittest.mock import patch

        from vibe3.agents.run_prompt import make_run_context_builder
        from vibe3.config.settings import VibeConfig

        config = VibeConfig.get_defaults()
        with patch(
            "vibe3.agents.run_prompt.build_run_prompt_body",
            return_value="assembled run body",
        ):
            cb = make_run_context_builder(None, config)
            text = cb()

        assert text == "assembled run body"
        assert cb.last_result is not None
        assert cb.last_result.recipe_key == "run.plan"

    def test_run_context_builder_no_longer_exports_build_run_context(self) -> None:
        """build_run_context (old name) must not exist in run_context_builder."""
        import vibe3.agents.run_prompt as mod

        assert not hasattr(
            mod, "build_run_context"
        ), "build_run_context should be deleted; use build_run_prompt_body"
