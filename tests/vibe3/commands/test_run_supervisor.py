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


def _patch_supervisor_runtime(
    monkeypatch,
    *,
    plan_text: str = (
        "# Orchestra Governance Scan\n\n"
        "## Issue Cleanup\n\n"
        "Use `vibe3 task status` to inspect the current queue.\n"
    ),
    repo: str | None = None,
) -> None:
    orchestra_config = run_module.OrchestraConfig(
        repo=repo,
        pid_file=Path(".git/vibe3/orchestra.pid"),
    )

    monkeypatch.setattr(
        run_module.OrchestraConfig,
        "from_settings",
        classmethod(lambda cls: orchestra_config),
    )
    monkeypatch.setattr(
        run_module,
        "OrchestraStatusService",
        lambda config: MagicMock(),
    )
    monkeypatch.setattr(
        run_module,
        "GovernanceService",
        lambda config, status_service: MagicMock(render_current_plan=lambda: plan_text),
    )
    monkeypatch.setattr(
        run_module.VibeConfig,
        "get_defaults",
        classmethod(
            lambda cls: MagicMock(
                run=MagicMock(run_prompt="Execute governance supervisor task")
            )
        ),
    )
    monkeypatch.setattr(
        run_module,
        "CodeagentExecutionService",
        lambda config: MagicMock(resolve_agent_options=lambda role: MagicMock()),
    )


class TestRunSupervisorOption:
    def test_help_shows_supervisor_option(self) -> None:
        result = runner.invoke(cli_app, ["run", "--help"])
        output = strip_ansi(result.output)
        assert result.exit_code == 0
        assert "supervisor" in output
        assert "governance input" in output

    def test_dry_run_outputs_rendered_governance_plan(self, monkeypatch) -> None:
        _patch_supervisor_runtime(monkeypatch)

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
        assert "vibe3 task status" in result.output

    def test_non_dry_run_prints_async_session_and_log(self, monkeypatch) -> None:
        _patch_supervisor_runtime(monkeypatch)
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
        _patch_supervisor_runtime(monkeypatch, repo="owner/repo")
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-supervisor-apply-issue-426",
            log_path=Path("temp/logs/vibe3-supervisor-apply-issue-426.async.log"),
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
        assert "Tmux session: vibe3-supervisor-apply-issue-426" in result.output
        assert (
            "Session log: temp/logs/vibe3-supervisor-apply-issue-426.async.log"
            in result.output
        )
        task = backend.start_async.call_args.kwargs["task"]
        assert "Process governance issue #426" in task
        assert "cleanup: orchestra smoke test residuals" in task
        assert "comment the outcome on the same issue" in task

    def test_issue_mode_uses_configured_supervisor_file(self, monkeypatch) -> None:
        _patch_supervisor_runtime(monkeypatch, repo="owner/repo")
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-supervisor-governance-apply-issue-426",
            log_path=Path(
                "temp/logs/vibe3-supervisor-governance-apply-issue-426.async.log"
            ),
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
        assert (
            "Tmux session: vibe3-supervisor-governance-apply-issue-426" in result.output
        )

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

    def test_manager_issue_mode_fresh_session_shows_in_help(self) -> None:
        result = runner.invoke(cli_app, ["run", "--help"])
        output = strip_ansi(result.output)
        assert result.exit_code == 0
        assert "fresh-session" in output

    def test_manager_issue_sync_failure_marks_issue_failed(self, monkeypatch) -> None:
        orchestra_config = run_module.OrchestraConfig(
            repo="owner/repo",
            pid_file=Path(".git/vibe3/orchestra.pid"),
        )
        monkeypatch.setattr(
            run_module.OrchestraConfig,
            "from_settings",
            classmethod(lambda cls: orchestra_config),
        )
        monkeypatch.setattr(
            run_module.VibeConfig,
            "get_defaults",
            classmethod(lambda cls: MagicMock()),
        )
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: MagicMock())
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: "ses_manager"
        )
        monkeypatch.setattr(
            run_module, "_resolve_manager_branch", lambda **kwargs: "task/issue-278"
        )
        monkeypatch.setattr(
            run_module,
            "_resolve_manager_execution_cwd",
            lambda **kwargs: (Path("/tmp/repo/.worktrees/issue-278"), False),
        )
        monkeypatch.setattr(
            run_module,
            "_resolve_manager_agent_options",
            lambda **kwargs: MagicMock(),
        )
        monkeypatch.setattr(
            run_module,
            "render_manager_prompt",
            lambda config, issue: MagicMock(rendered_text="manager prompt"),
        )
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            staticmethod(lambda: "dev/issue-435"),
        )

        github = MagicMock()
        github.view_issue.return_value = {
            "number": 278,
            "title": "test manager issue",
            "labels": [{"name": "state/claimed"}],
            "assignees": [],
        }
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)

        backend = MagicMock()
        backend.run.return_value = MagicMock(
            is_success=lambda: False,
            stderr="manager failed",
            session_id="ses_manager",
        )
        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)

        labels = MagicMock()
        monkeypatch.setattr(run_module, "LabelService", lambda: labels)

        result = runner.invoke(
            cli_app,
            ["run", "--manager-issue", "278", "--sync"],
        )

        assert result.exit_code != 0
        github.add_comment.assert_called_once()
        labels.confirm_issue_state.assert_called_once_with(
            278,
            run_module.IssueState.FAILED,
            actor="agent:manager",
            force=True,
        )

    def test_manager_issue_sync_noop_auto_blocks(self, monkeypatch) -> None:
        orchestra_config = run_module.OrchestraConfig(
            repo="owner/repo",
            pid_file=Path(".git/vibe3/orchestra.pid"),
        )
        monkeypatch.setattr(
            run_module.OrchestraConfig,
            "from_settings",
            classmethod(lambda cls: orchestra_config),
        )
        monkeypatch.setattr(
            run_module.VibeConfig,
            "get_defaults",
            classmethod(lambda cls: MagicMock()),
        )
        sqlite = MagicMock()
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: "ses_manager"
        )
        monkeypatch.setattr(
            run_module, "_resolve_manager_branch", lambda **kwargs: "task/issue-278"
        )
        monkeypatch.setattr(
            run_module,
            "_resolve_manager_execution_cwd",
            lambda **kwargs: (Path("/tmp/repo/.worktrees/issue-278"), False),
        )
        monkeypatch.setattr(
            run_module,
            "_resolve_manager_agent_options",
            lambda **kwargs: MagicMock(),
        )
        monkeypatch.setattr(
            run_module,
            "render_manager_prompt",
            lambda config, issue: MagicMock(rendered_text="manager prompt"),
        )
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            staticmethod(lambda: "dev/post-437-debug"),
        )
        monkeypatch.setattr(
            run_module,
            "_snapshot_manager_effects",
            lambda **kwargs: {
                "state_label": "state/ready",
                "comment_count": 1,
                "handoff": None,
                "refs": (None, None, None, None, None, None),
            },
        )
        block_noop = MagicMock()
        monkeypatch.setattr(run_module, "_block_manager_noop_issue", block_noop)

        github = MagicMock()
        github.view_issue.return_value = {
            "number": 278,
            "title": "test manager issue",
            "labels": [{"name": "state/ready"}],
            "assignees": [],
        }
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)

        backend = MagicMock()
        backend.run.return_value = MagicMock(
            is_success=lambda: True,
            stderr="",
            session_id="ses_manager",
        )
        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)

        result = runner.invoke(
            cli_app,
            ["run", "--manager-issue", "278", "--sync"],
        )

        assert result.exit_code == 0
        block_noop.assert_called_once()
        assert any(
            call.args[1] == "manager_noop_blocked"
            for call in sqlite.add_event.call_args_list
        )
