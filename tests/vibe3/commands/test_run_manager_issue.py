"""Tests for `vibe3 run --manager-issue` basic and session behavior."""

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

import vibe3.commands.run as run_module
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


def _patch_basic(monkeypatch, backend, github, sqlite=None, *, poll_session_id=False):
    # Patch manager_run_service's dependencies
    from vibe3.manager import manager_run_service
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
        manager_run_service, "load_session_id", lambda role, branch=None: None
    )
    monkeypatch.setattr(
        manager_run_service,
        "render_manager_prompt",
        lambda config, issue: MagicMock(rendered_text="# Manager 自动化执行材料\n"),
    )
    if not poll_session_id:
        monkeypatch.setattr(
            manager_run_service,
            "wait_for_async_session_id",
            lambda log_path, timeout_seconds=3.0: None,
        )


class TestRunManagerIssueMode:
    def test_prints_async_session_and_log(self, monkeypatch) -> None:
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: manager_run_service.OrchestraConfig.model_validate(
                    {
                        "pid_file": ".git/vibe3/orchestra.pid",
                        "assignee_dispatch": {"agent": "manager-orchestrator"},
                    }
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

    def test_does_not_use_run_context_builder(self, monkeypatch) -> None:
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

    def test_reports_github_timeout_clearly(self, monkeypatch) -> None:
        github = MagicMock()
        github.view_issue.return_value = "network_error"

        monkeypatch.setattr(manager_run_service, "GitHubClient", lambda: github)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code != 0
        assert "GitHub read timed out or auth/network is unavailable" in result.stderr

    def test_persists_async_session_id_from_log(self, monkeypatch, tmp_path) -> None:
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

        _patch_basic(monkeypatch, backend, github, sqlite, poll_session_id=True)
        monkeypatch.setattr(
            manager_run_service, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        sqlite.update_flow_state.assert_called_once()
        assert (
            sqlite.update_flow_state.call_args.kwargs["manager_session_id"]
            == "ses_manager372"
        )

    def test_persists_async_session_id_from_wrapper_log(
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

        _patch_basic(monkeypatch, backend, github, sqlite, poll_session_id=True)
        monkeypatch.setattr(
            manager_run_service, "load_session_id", lambda role, branch=None: None
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372"])

        assert result.exit_code == 0
        sqlite.update_flow_state.assert_called_once()
        assert (
            sqlite.update_flow_state.call_args.kwargs["manager_session_id"]
            == "ses_wrapper372"
        )

    def test_reuses_existing_session_for_launch_cwd(self, monkeypatch) -> None:
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service,
            "load_session_id",
            lambda role, branch=None: "ses_existing",
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--worktree"])

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] == "ses_existing"
        assert backend.start_async.call_args.kwargs["cwd"] == Path.cwd()

    def test_fresh_session_skips_session_resume(self, monkeypatch) -> None:
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
            manager_run_service,
            "load_session_id",
            lambda role, branch=None: "ses_existing",
        )

        result = runner.invoke(
            cli_app, ["run", "--manager-issue", "372", "--fresh-session"]
        )

        assert result.exit_code == 0
        assert backend.start_async.call_args.kwargs["session_id"] is None

    def test_sync_completion_clears_manager_session_id(self, monkeypatch) -> None:
        backend = _make_backend()
        backend.run.return_value = MagicMock(
            session_id="ses_manager372",
            is_success=MagicMock(return_value=True),
        )
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: manager_run_service.OrchestraConfig.model_validate(
                    {
                        "pid_file": ".git/vibe3/orchestra.pid",
                        "assignee_dispatch": {"agent": "manager-orchestrator"},
                    }
                )
            ),
        )
        monkeypatch.setattr(
            manager_run_service,
            "has_progress_changed",
            lambda before, after, **kwargs: True,
        )

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--sync"])

        assert result.exit_code == 0
        assert (
            sqlite.update_flow_state.call_args_list[-1].kwargs.get("manager_session_id")
            is None
        )

    def test_sync_dry_run_preserves_manager_session_id(self, monkeypatch) -> None:
        backend = _make_backend()
        backend.run.return_value = MagicMock(
            session_id="ses_manager372",
            is_success=MagicMock(return_value=True),
        )
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: manager_run_service.OrchestraConfig.model_validate(
                    {
                        "pid_file": ".git/vibe3/orchestra.pid",
                        "assignee_dispatch": {"agent": "manager-orchestrator"},
                    }
                )
            ),
        )

        result = runner.invoke(
            cli_app,
            ["run", "--manager-issue", "372", "--sync", "--dry-run"],
        )

        assert result.exit_code == 0
        assert not sqlite.update_flow_state.called

    def test_sync_dry_run_failure_does_not_fail_issue(self, monkeypatch) -> None:
        backend = _make_backend()
        backend.run.side_effect = RuntimeError("dry-run backend failed")
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: manager_run_service.OrchestraConfig.model_validate(
                    {
                        "pid_file": ".git/vibe3/orchestra.pid",
                        "assignee_dispatch": {"agent": "manager-orchestrator"},
                    }
                )
            ),
        )

        result = runner.invoke(
            cli_app,
            ["run", "--manager-issue", "372", "--sync", "--dry-run"],
        )

        assert result.exit_code != 0
        assert not sqlite.add_event.called
        github.add_comment.assert_not_called()

    # === No-progress parity tests ===

    def test_sync_path_blocks_on_comment_only_change_for_ready(
        self, monkeypatch
    ) -> None:
        """READY state requires state transition; comments alone are NOT progress."""
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: manager_run_service.OrchestraConfig.model_validate(
                    {
                        "pid_file": ".git/vibe3/orchestra.pid",
                        "assignee_dispatch": {"agent": "manager-orchestrator"},
                    }
                )
            ),
        )

        # Mock progress detection
        before_snapshot = {
            "state_label": "state/ready",
            "comment_count": 5,
            "handoff": "handoff_sig_before",
            "refs": {"plan_ref": "/tmp/plan.md"},
            "issue_state": "open",
        }
        after_snapshot = {
            "state_label": "state/ready",  # State unchanged
            "comment_count": 6,  # Comment count increased
            "handoff": "handoff_sig_before",
            "refs": {"plan_ref": "/tmp/plan.md"},
            "issue_state": "open",
        }

        snapshot_calls = 0

        def mock_snapshot(*args, **kwargs):
            nonlocal snapshot_calls
            snapshot_calls += 1
            return after_snapshot if snapshot_calls > 1 else before_snapshot

        # Mock the shared snapshot_progress function
        monkeypatch.setattr(manager_run_service, "snapshot_progress", mock_snapshot)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--sync"])

        assert result.exit_code == 0
        # SHOULD block because state unchanged (READY requires transition)
        github.add_comment.assert_called_once()
        comment = github.add_comment.call_args[0][1]
        assert "未产生状态迁移" in comment

    def test_sync_path_blocks_on_handoff_only_change_for_ready(
        self, monkeypatch
    ) -> None:
        """READY state requires state transition; handoff change alone is NOT
        progress."""
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: manager_run_service.OrchestraConfig.model_validate(
                    {
                        "pid_file": ".git/vibe3/orchestra.pid",
                        "assignee_dispatch": {"agent": "manager-orchestrator"},
                    }
                )
            ),
        )

        before_snapshot = {
            "state_label": "state/ready",
            "comment_count": 5,
            "handoff": "handoff_sig_before",
            "refs": {"plan_ref": "/tmp/plan.md"},
            "issue_state": "open",
        }
        after_snapshot = {
            "state_label": "state/ready",  # State unchanged
            "comment_count": 5,
            "handoff": "handoff_sig_after",  # Handoff changed
            "refs": {"plan_ref": "/tmp/plan.md"},
            "issue_state": "open",
        }

        snapshot_calls = 0

        def mock_snapshot(*args, **kwargs):
            nonlocal snapshot_calls
            snapshot_calls += 1
            return after_snapshot if snapshot_calls > 1 else before_snapshot

        monkeypatch.setattr(manager_run_service, "snapshot_progress", mock_snapshot)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--sync"])

        assert result.exit_code == 0
        # SHOULD block because state unchanged (READY requires transition)
        github.add_comment.assert_called_once()
        comment = github.add_comment.call_args[0][1]
        assert "未产生状态迁移" in comment

    def test_sync_no_progress_block_fires_for_truly_no_change(
        self, monkeypatch
    ) -> None:
        """No-progress block should fire when truly no observable change."""
        backend = _make_backend()
        github = _make_github()
        sqlite = MagicMock()

        _patch_basic(monkeypatch, backend, github, sqlite)
        monkeypatch.setattr(
            manager_run_service.OrchestraConfig,
            "from_settings",
            staticmethod(
                lambda: manager_run_service.OrchestraConfig.model_validate(
                    {
                        "pid_file": ".git/vibe3/orchestra.pid",
                        "assignee_dispatch": {"agent": "manager-orchestrator"},
                    }
                )
            ),
        )

        before_snapshot = {
            "state_label": "state/ready",
            "comment_count": 5,
            "handoff": "handoff_sig",
            "refs": {"plan_ref": "/tmp/plan.md"},
        }
        after_snapshot = before_snapshot.copy()  # No change at all

        snapshot_calls = 0

        def mock_snapshot(*args, **kwargs):
            nonlocal snapshot_calls
            snapshot_calls += 1
            return after_snapshot if snapshot_calls > 1 else before_snapshot

        monkeypatch.setattr(manager_run_service, "snapshot_progress", mock_snapshot)

        result = runner.invoke(cli_app, ["run", "--manager-issue", "372", "--sync"])

        assert result.exit_code == 0
        # Should block because no change at all
        github.add_comment.assert_called_once()
        comment = github.add_comment.call_args[0][1]
        assert "[manager]" in comment
        assert "未产生状态迁移" in comment
