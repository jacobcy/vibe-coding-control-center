"""Tests for `vibe3 run --supervisor`."""

import re
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

import vibe3.commands.run as run_module
from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.cli import app as cli_app

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestRunSupervisorOption:
    def test_help_shows_supervisor_option(self) -> None:
        result = runner.invoke(cli_app, ["run", "--help"])
        output = strip_ansi(result.output)
        assert result.exit_code == 0
        assert "supervisor" in output
        assert "governance input" in output


    def test_dry_run_outputs_rendered_governance_plan(self) -> None:
        result = runner.invoke(
            cli_app,
            [
                "run",
                "--supervisor",
                "supervisor/issue-cleanup.md",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0
        assert "Supervisor dry run" in result.output
        assert "# Orchestra Governance Scan" in result.output
        assert "Issue Cleanup" in result.output or "cleanup" in result.output.lower()
        assert "vibe3 status" in result.output

    def test_non_dry_run_prints_async_session_and_log(self, monkeypatch) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-supervisor-issue-cleanup",
            log_path=Path("temp/logs/vibe3-supervisor-issue-cleanup.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)

        result = runner.invoke(
            cli_app,
            [
                "run",
                "--supervisor",
                "supervisor/issue-cleanup.md",
            ],
        )

        assert result.exit_code == 0
        assert "Supervisor run: supervisor/issue-cleanup.md" in result.output
        assert "Tmux session: vibe3-supervisor-issue-cleanup" in result.output
        assert (
            "Session log: temp/logs/vibe3-supervisor-issue-cleanup.async.log"
            in result.output
        )
        backend.start_async.assert_called_once()

    def test_issue_mode_defaults_to_supervisor_apply(self, monkeypatch) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-supervisor-apply",
            log_path=Path("temp/logs/vibe3-supervisor-apply.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 426,
            "title": "cleanup: orchestra smoke test residuals (issues #369, #370)",
        }
        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(
            run_module,
            "_resolve_issue_supervisor_file",
            lambda: "supervisor/apply.md",
        )

        result = runner.invoke(cli_app, ["run", "--issue", "426"])

        assert result.exit_code == 0
        assert "Supervisor run: supervisor/apply.md" in result.output
        task = backend.start_async.call_args.kwargs["task"]
        assert "Process governance issue #426" in task
        assert "cleanup: orchestra smoke test residuals" in task
        assert "comment the outcome on the same issue" in task

    def test_issue_mode_uses_configured_supervisor_file(self, monkeypatch) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-supervisor-governance-apply",
            log_path=Path("temp/logs/vibe3-supervisor-governance-apply.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 426,
            "title": "cleanup: orchestra smoke test residuals (issues #369, #370)",
        }
        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(
            run_module,
            "_resolve_issue_supervisor_file",
            lambda: "supervisor/governance-apply.md",
        )

        result = runner.invoke(cli_app, ["run", "--issue", "426"])

        assert result.exit_code == 0
        assert "Supervisor run: supervisor/governance-apply.md" in result.output

    def test_issue_mode_rejects_other_run_modes(self) -> None:
        result = runner.invoke(
            cli_app,
            ["run", "--issue", "426", "--skill", "vibe-new"],
        )

        assert result.exit_code != 0
        assert (
            "--issue cannot be combined with --plan, --skill, or --supervisor."
            in result.stderr
        )
