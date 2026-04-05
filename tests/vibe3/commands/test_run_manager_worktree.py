"""Tests for `vibe3 run --manager-issue` flow resolution and worktree behavior."""

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.cli import app as cli_app
from vibe3.manager import manager_run_service

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
    from vibe3.services import issue_failure_service

    monkeypatch.setattr(manager_run_service, "CodeagentBackend", lambda: backend)
    monkeypatch.setattr(manager_run_service, "GitHubClient", lambda: github)
    monkeypatch.setattr(issue_failure_service, "GitHubClient", lambda: github)
    monkeypatch.setattr(
        manager_run_service, "SQLiteClient", lambda: sqlite or MagicMock()
    )
    monkeypatch.setattr(
        manager_run_service.GitClient,
        "get_current_branch",
        lambda self: "dev/issue-430",
    )
    monkeypatch.setattr(
        manager_run_service,
        "render_manager_prompt",
        lambda config, issue: MagicMock(rendered_text="# Manager prompt\n"),
    )
    monkeypatch.setattr(
        manager_run_service,
        "wait_for_async_session_id",
        lambda log_path, timeout_seconds=3.0: None,
    )


class TestRunManagerFlowResolution:
    def test_prefers_target_issue_flow_branch(self, monkeypatch) -> None:
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
            manager_run_service,
            "load_session_id",
            lambda role, branch=None: "ses_target",
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] == "ses_target"
        sqlite.add_event.assert_called_once()
        assert sqlite.add_event.call_args.args[0] == "task/issue-372"

    def test_prefers_active_flow_over_aborted_session_flow(self, monkeypatch) -> None:
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
        monkeypatch.setattr(manager_run_service, "load_session_id", load_session)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] is None
        assert sqlite.add_event.call_args.args[0] == "task/issue-372"

    def test_uses_canonical_target_branch_without_target_flow(
        self, monkeypatch
    ) -> None:
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()
        sqlite.get_flows_by_issue.return_value = []

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        sqlite.add_event.assert_called_once()
        assert sqlite.add_event.call_args.args[0] == "task/issue-372"


class TestRunManagerWorktree:
    def test_skips_worktree_when_scene_exists(self, monkeypatch) -> None:
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
            manager_run_service.GitClient,
            "get_git_common_dir",
            lambda self: "/Users/jacobcy/src/vibe-center/main/.git",
        )
        monkeypatch.setattr(
            "vibe3.manager.worktree_manager.WorktreeManager",
            lambda config, repo_root: worktree_manager,
        )
        monkeypatch.setattr(
            manager_run_service, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--worktree"])

        assert result.exit_code == 0
        options = backend.start_async.call_args.kwargs["options"]
        assert options.worktree is False
        assert backend.start_async.call_args.kwargs["cwd"] == Path(
            "/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"
        )

    def test_uses_repo_root_cwd_for_first_worktree_launch(self, monkeypatch) -> None:
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()
        worktree_manager = MagicMock()
        worktree_manager.resolve_manager_cwd.return_value = (
            Path("/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"),
            False,
        )

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service.GitClient,
            "get_git_common_dir",
            lambda self: "/Users/jacobcy/src/vibe-center/main/.git",
        )
        monkeypatch.setattr(
            "vibe3.manager.worktree_manager.WorktreeManager",
            lambda config, repo_root: worktree_manager,
        )
        monkeypatch.setattr(
            manager_run_service, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--worktree"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["cwd"] == Path(
            "/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"
        )

    def test_uses_target_scene_cwd_for_foreign_flow(self, monkeypatch) -> None:
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
            manager_run_service.GitClient,
            "get_git_common_dir",
            lambda self: "/Users/jacobcy/src/vibe-center/main/.git",
        )
        monkeypatch.setattr(
            manager_run_service, "load_session_id", lambda role, branch=None: None
        )
        monkeypatch.setattr(
            "vibe3.manager.worktree_manager.WorktreeManager",
            lambda config, repo_root: worktree_manager,
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["cwd"] == Path(
            "/Users/jacobcy/src/vibe-center/main/.worktrees/issue-372"
        )

    def test_uses_repo_root_for_first_worktree_on_foreign_flow(
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
            manager_run_service.GitClient,
            "get_git_common_dir",
            lambda self: "/Users/jacobcy/src/vibe-center/main/.git",
        )
        monkeypatch.setattr(
            manager_run_service, "load_session_id", lambda role, branch=None: None
        )
        monkeypatch.setattr(
            "vibe3.manager.worktree_manager.WorktreeManager",
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
