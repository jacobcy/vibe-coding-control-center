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
        assert "vibe3 task status" in result.output

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

    def test_manager_issue_mode_prints_async_session_and_log(self, monkeypatch) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: run_module.OrchestraConfig.model_validate(
                    {
                        "assignee_dispatch": {
                            "agent": "manager-orchestrator",
                        }
                    }
                )
            ),
        )
        monkeypatch.setattr(
            run_module.GitClient, "get_current_branch", lambda self: "dev/issue-430"
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert "Manager run: issue #372" in result.output
        assert "Tmux session: vibe3-manager-issue-372" in result.output
        assert (
            "Session log: temp/logs/vibe3-manager-issue-372.async.log" in result.output
        )
        backend.start_async.assert_called_once()
        assert (
            backend.start_async.call_args.kwargs["options"].agent
            == "manager-orchestrator"
        )

    def test_manager_issue_mode_does_not_use_run_context_builder(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "manager state machine test",
            "labels": [],
        }
        sqlite = MagicMock()

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module,
            "make_run_context_builder",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("manager must not use run context builder")
            ),
        )
        monkeypatch.setattr(
            run_module.GitClient, "get_current_branch", lambda self: "dev/issue-430"
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["prompt"].startswith(
            "# Manager 自动化执行材料"
        )
        assert "Manage issue #372" in backend.start_async.call_args.kwargs["task"]

    def test_manager_issue_mode_reports_github_timeout_clearly(
        self, monkeypatch
    ) -> None:
        github = MagicMock()
        github.view_issue.return_value = "network_error"

        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code != 0
        assert "GitHub read timed out or auth/network is unavailable" in result.stderr

    def test_manager_issue_skips_worktree_when_scene_exists(self, monkeypatch) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = [
            {
                "branch": "task/issue-372",
                "flow_status": "active",
                "manager_session_id": None,
                "updated_at": "2026-04-03T12:00:00",
            }
        ]
        worktree_manager = MagicMock()
        worktree_manager.resolve_manager_cwd.return_value = (
            Path("/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"),
            False,
        )

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module.GitClient,
            "get_git_common_dir",
            lambda self: "/Users/jacobcy/src/vibe-center/main/.git",
        )
        monkeypatch.setattr(
            run_module,
            "WorktreeManager",
            lambda config, repo_root: worktree_manager,
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--worktree"])

        assert result.exit_code == 0
        options = backend.start_async.call_args.kwargs["options"]
        assert options.worktree is False
        assert backend.start_async.call_args.kwargs["cwd"] == Path(
            "/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"
        )

    def test_manager_issue_mode_uses_repo_root_cwd_for_first_worktree_launch(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module.GitClient,
            "get_git_common_dir",
            lambda self: "/Users/jacobcy/src/vibe-center/main/.git",
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--worktree"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["cwd"] == Path(
            "/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"
        )

    def test_manager_issue_mode_persists_async_session_id_from_log(
        self, monkeypatch, tmp_path
    ) -> None:
        log_path = tmp_path / "vibe3-manager-issue-372.async.log"
        log_path.write_text("SESSION_ID: ses_manager372\n")

        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=log_path,
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        sqlite.update_flow_state.assert_called_once()
        assert (
            sqlite.update_flow_state.call_args.kwargs["manager_session_id"]
            == "ses_manager372"
        )

    def test_manager_issue_mode_persists_async_session_id_from_wrapper_log(
        self, monkeypatch, tmp_path
    ) -> None:
        wrapper_log = tmp_path / "codeagent-wrapper-53796.log"
        wrapper_log.write_text('{"type":"step_start","sessionID":"ses_wrapper372"}\n')
        log_path = tmp_path / "vibe3-manager-issue-372.async.log"
        log_path.write_text(f"[codeagent-wrapper]\n  Log: {wrapper_log}\n")

        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=log_path,
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        sqlite.update_flow_state.assert_called_once()
        assert (
            sqlite.update_flow_state.call_args.kwargs["manager_session_id"]
            == "ses_wrapper372"
        )

    def test_manager_issue_mode_reuses_existing_session_for_launch_cwd(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: "ses_existing"
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--worktree"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] == "ses_existing"
        assert backend.start_async.call_args.kwargs["cwd"] == Path.cwd()

    def test_manager_issue_mode_prefers_target_issue_flow_branch(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = [
            {
                "branch": "task/issue-372",
                "manager_session_id": "ses_target",
                "updated_at": "2026-04-03T12:00:00",
            }
        ]

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: "ses_target"
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] == "ses_target"
        sqlite.add_event.assert_called_once()
        assert sqlite.add_event.call_args.args[0] == "task/issue-372"

    def test_manager_issue_mode_prefers_active_flow_over_aborted_session_flow(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = [
            {
                "branch": "do/20260403-aaf82f",
                "flow_status": "aborted",
                "manager_session_id": "ses_old",
                "updated_at": "2026-04-03T12:59:00",
            },
            {
                "branch": "task/issue-372",
                "flow_status": "active",
                "manager_session_id": None,
                "updated_at": "2026-04-01T19:50:00",
            },
        ]

        def load_session(role: str, branch: str | None = None) -> str | None:
            if branch == "task/issue-372":
                return None
            if branch == "do/20260403-aaf82f":
                return "ses_old"
            return None

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(run_module, "load_session_id", load_session)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] is None
        assert sqlite.add_event.call_args.args[0] == "task/issue-372"

    def test_manager_issue_mode_uses_target_scene_cwd_for_foreign_flow(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = [
            {
                "branch": "task/issue-372",
                "flow_status": "active",
                "manager_session_id": None,
                "updated_at": "2026-04-03T12:00:00",
            }
        ]
        worktree_manager = MagicMock()
        worktree_manager.resolve_manager_cwd.return_value = (
            Path("/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"),
            False,
        )

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module.GitClient,
            "get_git_common_dir",
            lambda self: "/Users/jacobcy/src/vibe-center/main/.git",
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: None
        )
        monkeypatch.setattr(
            run_module,
            "WorktreeManager",
            lambda config, repo_root: worktree_manager,
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["cwd"] == Path(
            "/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"
        )

    def test_manager_issue_mode_uses_repo_root_for_first_worktree_on_foreign_flow(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = [
            {
                "branch": "task/issue-372",
                "flow_status": "active",
                "manager_session_id": None,
                "updated_at": "2026-04-03T12:00:00",
            }
        ]
        worktree_manager = MagicMock()

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module.GitClient,
            "get_git_common_dir",
            lambda self: "/Users/jacobcy/src/vibe-center/main/.git",
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: None
        )
        monkeypatch.setattr(
            run_module,
            "WorktreeManager",
            lambda config, repo_root: worktree_manager,
        )
        worktree_manager.resolve_manager_cwd.return_value = (None, False)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--worktree"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["cwd"] == Path(
            "/Users/jacobcy/src/vibe-center/main"
        )
        options = backend.start_async.call_args.kwargs["options"]
        assert options.worktree is True
        worktree_manager.resolve_manager_cwd.assert_called_once()

    def test_manager_issue_mode_fresh_session_skips_session_resume(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "fresh session test",
            "labels": [],
        }
        sqlite = MagicMock()

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        # Even though a session exists, --fresh-session should ignore it
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: "ses_existing"
        )

        result = runner.invoke(
            cli_app, ["run", "--manager-issue", "372", "--fresh-session"]
        )

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] is None

    def test_manager_issue_mode_fresh_session_shows_in_help(self) -> None:
        result = runner.invoke(cli_app, ["run", "--help"])
        output = strip_ansi(result.output)
        assert result.exit_code == 0
        assert "fresh-session" in output

    def test_manager_issue_mode_uses_canonical_target_branch_without_target_flow(
        self, monkeypatch
    ) -> None:
        backend = MagicMock()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
            "labels": [],
        }
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = []

        monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
        monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
        monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite)
        monkeypatch.setattr(
            run_module.GitClient,
            "get_current_branch",
            lambda self: "dev/issue-430",
        )
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        sqlite.add_event.assert_called_once()
        assert sqlite.add_event.call_args.args[0] == "task/issue-372"
