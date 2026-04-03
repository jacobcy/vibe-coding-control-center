"""Tests for `vibe3 run --manager-issue` mode."""

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

import vibe3.commands.run as run_module
from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.cli import app as cli_app

runner = CliRunner(env={"NO_COLOR": "1"})


def _make_backend():
    backend = MagicMock()
    backend.start_async.return_value = AsyncExecutionHandle(
        tmux_session="vibe3-manager-issue-372",
        log_path=Path("temp/logs/vibe3-manager-issue-372.async.log"),
        prompt_file_path=Path("/tmp/prompt.md"),
    )
    return backend


def _make_github():
    github = MagicMock()
    github.view_issue.return_value = {
        "number": 372,
        "title": "chore(orchestra): 发布接手与验收执行（manager worktree 闭环）",
        "labels": [],
    }
    return github


def _patch_basic(monkeypatch, backend, github, sqlite=None):
    monkeypatch.setattr(run_module, "CodeagentBackend", lambda: backend)
    monkeypatch.setattr(run_module, "GitHubClient", lambda: github)
    monkeypatch.setattr(run_module, "SQLiteClient", lambda: sqlite or MagicMock())
    monkeypatch.setattr(
        run_module.GitClient, "get_current_branch", lambda self: "dev/issue-430"
    )


class TestRunManagerIssueMode:
    def test_manager_issue_mode_prints_async_session_and_log(self, monkeypatch) -> None:
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            run_module.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: run_module.OrchestraConfig.model_validate(
                    {"assignee_dispatch": {"agent": "manager-orchestrator"}}
                )
            ),
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
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            run_module,
            "make_run_context_builder",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("manager must not use run context builder")
            ),
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
        backend = _make_backend()
        github = _make_github()
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

        _patch_basic(monkeypatch, backend, github, sqlite)
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
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
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

        backend = _make_backend()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=log_path,
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
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

        backend = _make_backend()
        backend.start_async.return_value = AsyncExecutionHandle(
            tmux_session="vibe3-manager-issue-372",
            log_path=log_path,
            prompt_file_path=Path("/tmp/prompt.md"),
        )
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
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
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
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
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = [
            {
                "branch": "task/issue-372",
                "manager_session_id": "ses_target",
                "updated_at": "2026-04-03T12:00:00",
            }
        ]

        _patch_basic(monkeypatch, backend, github, sqlite)
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
        backend = _make_backend()
        github = _make_github()
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

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(run_module, "load_session_id", load_session)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] is None
        assert sqlite.add_event.call_args.args[0] == "task/issue-372"

    def test_manager_issue_mode_uses_target_scene_cwd_for_foreign_flow(
        self, monkeypatch
    ) -> None:
        backend = _make_backend()
        github = _make_github()
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

        _patch_basic(monkeypatch, backend, github, sqlite)
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
        backend = _make_backend()
        github = _make_github()
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
        worktree_manager.resolve_manager_cwd.return_value = (None, False)

        _patch_basic(monkeypatch, backend, github, sqlite)
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
        backend = _make_backend()
        github = MagicMock()
        github.view_issue.return_value = {
            "number": 372,
            "title": "fresh session test",
            "labels": [],
        }
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        # Even though a session exists, --fresh-session should ignore it
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: "ses_existing"
        )

        result = runner.invoke(
            cli_app, ["run", "--manager-issue", "372", "--fresh-session"]
        )

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] is None

    def test_manager_issue_mode_uses_canonical_target_branch_without_target_flow(
        self, monkeypatch
    ) -> None:
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = []

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            run_module, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        sqlite.add_event.assert_called_once()
        assert sqlite.add_event.call_args.args[0] == "task/issue-372"
