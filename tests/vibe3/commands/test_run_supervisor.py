"""Tests for `vibe3 run --supervisor`."""

import re
from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.cli import app as cli_app
from vibe3.config.settings import VibeConfig
from vibe3.manager import manager_run_service
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.services import issue_failure_service

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
    orchestra_config = OrchestraConfig(
        repo=repo,
        pid_file=Path(".git/vibe3/orchestra.pid"),
    )

    monkeypatch.setattr(
        OrchestraConfig,
        "from_settings",
        classmethod(lambda cls: orchestra_config),
    )
    # Patch both command module and service module imports
    from vibe3.orchestra import supervisor_run_service

    monkeypatch.setattr(
        supervisor_run_service,
        "OrchestraStatusService",
        lambda config, orchestrator: MagicMock(),
    )
    monkeypatch.setattr(
        supervisor_run_service,
        "GovernanceService",
        lambda config, status_service: MagicMock(render_current_plan=lambda: plan_text),
    )
    monkeypatch.setattr(
        supervisor_run_service.VibeConfig,
        "get_defaults",
        classmethod(
            lambda cls: MagicMock(
                run=MagicMock(run_prompt="Execute governance supervisor task")
            )
        ),
    )
    monkeypatch.setattr(
        supervisor_run_service,
        "CodeagentExecutionService",
        lambda config: MagicMock(resolve_agent_options=lambda role: MagicMock()),
    )


class TestRunSupervisorOption:
    def test_help_shows_supervisor_option(self) -> None:
        # Check internal apply help instead of run help
        result = runner.invoke(cli_app, ["internal", "apply", "--help"])
        output = strip_ansi(result.output)
        assert result.exit_code == 0
        assert "supervisor" in output.lower()

    def test_dry_run_outputs_rendered_governance_plan(self, monkeypatch) -> None:
        _patch_supervisor_runtime(monkeypatch)

        result = runner.invoke(
            cli_app,
            [
                "internal",
                "apply",
                "supervisor/issue-cleanup.md",
                "--dry-run",
                "--no-async",
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
        from vibe3.orchestra import supervisor_run_service

        monkeypatch.setattr(supervisor_run_service, "CodeagentBackend", lambda: backend)

        result = runner.invoke(
            cli_app,
            [
                "internal",
                "apply",
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

    def test_issue_mode_dispatch(self, monkeypatch) -> None:
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
        from vibe3.orchestra import supervisor_run_service

        monkeypatch.setattr(supervisor_run_service, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(supervisor_run_service, "GitHubClient", lambda: github)

        result = runner.invoke(
            cli_app, ["internal", "apply", "supervisor/apply.md", "--issue", "426"]
        )

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

    def test_manager_issue_sync_failure_marks_issue_failed(self, monkeypatch) -> None:
        orchestra_config = OrchestraConfig(
            repo="owner/repo",
            pid_file=Path(".git/vibe3/orchestra.pid"),
        )
        # Ensure assignee_dispatch is configured to avoid run-defaults fallback
        orchestra_config.assignee_dispatch.agent = "manager-agent"

        monkeypatch.setattr(
            OrchestraConfig,
            "from_settings",
            classmethod(lambda cls: orchestra_config),
        )
        monkeypatch.setattr(
            VibeConfig,
            "get_defaults",
            classmethod(lambda cls: VibeConfig()),
        )
        monkeypatch.setattr(manager_run_service, "SQLiteClient", lambda: MagicMock())
        monkeypatch.setattr(
            manager_run_service,
            "load_session_id",
            lambda role, branch=None: "ses_manager",
        )
        monkeypatch.setattr(
            manager_run_service,
            "resolve_manager_branch",
            lambda **kwargs: "task/issue-278",
        )
        monkeypatch.setattr(
            manager_run_service,
            "resolve_manager_execution_cwd",
            lambda **kwargs: (Path("/tmp/repo/.worktrees/issue-278"), False),
        )
        monkeypatch.setattr(
            manager_run_service,
            "render_manager_prompt",
            lambda config, issue: MagicMock(rendered_text="manager prompt"),
        )

        github = MagicMock()
        github.view_issue.return_value = {
            "number": 278,
            "title": "test manager issue",
            "labels": [{"name": "state/claimed"}],
            "assignees": [],
        }
        monkeypatch.setattr(manager_run_service, "GitHubClient", lambda: github)

        # IMPORTANT: Patch the class, not the instance factory if possible,
        # but here we patch what the service uses.
        monkeypatch.setattr(issue_failure_service, "GitHubClient", lambda: github)

        backend = MagicMock()
        backend.run.return_value = MagicMock(
            is_success=lambda: False,
            stderr="manager failed",
            session_id="ses_manager",
        )
        monkeypatch.setattr(manager_run_service, "CodeagentBackend", lambda: backend)

        labels = MagicMock()
        monkeypatch.setattr(issue_failure_service, "LabelService", lambda: labels)

        result = runner.invoke(
            cli_app,
            ["internal", "manager", "278", "--no-async"],
        )

        assert result.exit_code != 0
        github.add_comment.assert_called_once()
        labels.confirm_issue_state.assert_called_once_with(
            278,
            IssueState.FAILED,
            actor="agent:manager",
            force=True,
        )

    def test_manager_issue_sync_noop_auto_blocks(self, monkeypatch) -> None:
        orchestra_config = OrchestraConfig(
            repo="owner/repo",
            pid_file=Path(".git/vibe3/orchestra.pid"),
        )
        orchestra_config.assignee_dispatch.agent = "manager-agent"

        monkeypatch.setattr(
            OrchestraConfig,
            "from_settings",
            classmethod(lambda cls: orchestra_config),
        )
        monkeypatch.setattr(
            VibeConfig,
            "get_defaults",
            classmethod(lambda cls: VibeConfig()),
        )
        sqlite = MagicMock()
        monkeypatch.setattr(manager_run_service, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            manager_run_service,
            "load_session_id",
            lambda role, branch=None: "ses_manager",
        )
        monkeypatch.setattr(
            manager_run_service,
            "resolve_manager_branch",
            lambda **kwargs: "task/issue-278",
        )
        monkeypatch.setattr(
            manager_run_service,
            "resolve_manager_execution_cwd",
            lambda **kwargs: (Path("/tmp/repo/.worktrees/issue-278"), False),
        )
        monkeypatch.setattr(
            manager_run_service,
            "render_manager_prompt",
            lambda config, issue: MagicMock(rendered_text="manager prompt"),
        )
        monkeypatch.setattr(
            "vibe3.runtime.no_progress_policy.snapshot_progress",
            lambda **kwargs: {
                "state_label": "state/ready",
                "comment_count": 1,
                "handoff": None,
                "refs": (None, None, None, None, None, None),
            },
        )
        # Mock the coordinator's block_manager_noop_issue
        from vibe3.manager import manager_run_coordinator

        block_noop = MagicMock()
        monkeypatch.setattr(
            manager_run_coordinator,
            "block_manager_noop_issue",
            block_noop,
        )

        github = MagicMock()
        github.view_issue.return_value = {
            "number": 278,
            "title": "test manager issue",
            "labels": [{"name": "state/ready"}],
            "assignees": [],
        }
        monkeypatch.setattr(manager_run_service, "GitHubClient", lambda: github)

        backend = MagicMock()
        backend.run.return_value = MagicMock(
            is_success=lambda: True,
            stderr="",
            session_id="ses_manager",
        )
        monkeypatch.setattr(manager_run_service, "CodeagentBackend", lambda: backend)

        result = runner.invoke(
            cli_app,
            ["internal", "manager", "278", "--no-async"],
        )

        assert result.exit_code == 0
        block_noop.assert_called_once()
        assert any(
            call.args[1] == "manager_noop_blocked"
            for call in sqlite.add_event.call_args_list
        )
