"""Tests for orchestra manager cwd resolution and worktree management."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.vibe3.conftest import CompletedProcess
from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


def make_config() -> OrchestraConfig:
    return OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid"))


class TestManagerCwdResolution:
    """Tests for ManagerExecutor worktree management methods."""

    def test_resolve_manager_cwd_uses_current_branch(self):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager.worktree_manager, "_is_current_branch", return_value=True
        ):
            cwd, is_temp = manager._resolve_manager_cwd(88, "task/issue-88")

        assert cwd == Path("/tmp/repo")
        assert is_temp is False

    def test_resolve_manager_cwd_uses_existing_branch_worktree(self):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager.worktree_manager, "_is_current_branch", return_value=False
        ):
            with patch.object(
                manager.worktree_manager,
                "_find_worktree_for_branch",
                return_value=Path("/tmp/wt-issue-88"),
            ):
                cwd, is_temp = manager._resolve_manager_cwd(88, "task/issue-88")

        assert cwd == Path("/tmp/wt-issue-88")
        assert is_temp is False

    def test_resolve_manager_cwd_creates_worktree_when_missing(self):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager.worktree_manager, "_is_current_branch", return_value=False
        ):
            with patch.object(
                manager.worktree_manager,
                "_find_worktree_for_branch",
                return_value=None,
            ):
                with patch.object(
                    manager.worktree_manager,
                    "_ensure_manager_worktree",
                    return_value=(Path("/tmp/repo/.worktrees/issue-88"), True),
                ):
                    cwd, is_temp = manager._resolve_manager_cwd(88, "task/issue-88")

        assert cwd == Path("/tmp/repo/.worktrees/issue-88")
        assert is_temp is True

    def test_ensure_manager_worktree_creates_new_worktree(self, tmp_path: Path):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=tmp_path)

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(returncode=0),
        ) as mock_run:
            with patch(
                "vibe3.manager.worktree_manager.append_orchestra_event"
            ) as mock_append_event:
                path, is_temp = manager._ensure_manager_worktree(77, "task/issue-77")

        assert path == tmp_path / ".worktrees" / "issue-77"
        assert is_temp is True
        assert mock_run.call_args.args[0][:3] == ["git", "worktree", "add"]
        assert mock_run.call_args.kwargs["cwd"] == tmp_path
        mock_append_event.assert_called_once()
        assert mock_append_event.call_args.args[0] == "worktree"
        assert "created issue #77" in mock_append_event.call_args.args[1]
        assert "task/issue-77" in mock_append_event.call_args.args[1]
        assert str(tmp_path / ".worktrees" / "issue-77") in (
            mock_append_event.call_args.args[1]
        )
        assert mock_append_event.call_args.kwargs["repo_root"] == tmp_path

    def test_ensure_manager_worktree_does_not_log_event_on_creation_failure(
        self, tmp_path: Path
    ):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=tmp_path)

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(returncode=1, stderr="boom"),
        ):
            with patch(
                "vibe3.manager.worktree_manager.append_orchestra_event"
            ) as mock_append_event:
                path, is_temp = manager._ensure_manager_worktree(77, "task/issue-77")

        assert path is None
        assert is_temp is False
        mock_append_event.assert_not_called()

    def test_ensure_manager_worktree_skips_when_path_exists(self, tmp_path: Path):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=tmp_path)
        existing = tmp_path / ".worktrees" / "issue-77"
        existing.mkdir(parents=True)
        (existing / ".git").write_text("gitdir: /tmp/mock")

        with patch.object(
            manager.worktree_manager,
            "_find_worktree_for_branch",
            return_value=existing,
        ):
            with patch("subprocess.run") as mock_run:
                result = manager._ensure_manager_worktree(77, "task/issue-77")

        assert result == (existing, False)
        mock_run.assert_not_called()

    def test_ensure_manager_worktree_recycles_orphan_path(self, tmp_path: Path):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=tmp_path)
        orphan = tmp_path / ".worktrees" / "issue-77"
        orphan.mkdir(parents=True)
        (orphan / "stale.txt").write_text("orphan")

        def mock_run(cmd, *args, **kwargs):
            if cmd[:3] == ["git", "worktree", "remove"]:
                import shutil

                shutil.rmtree(orphan)
            return CompletedProcess(returncode=0)

        with patch(
            "subprocess.run",
            side_effect=mock_run,
        ) as mock_run:
            path, is_temp = manager._ensure_manager_worktree(77, "task/issue-77")

        assert path == orphan
        assert is_temp is True
        assert not (orphan / "stale.txt").exists()
        assert mock_run.call_args.args[0][:3] == ["git", "worktree", "add"]

    def test_ensure_manager_worktree_recycles_mismatched_git_path(self, tmp_path: Path):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=tmp_path)
        target = tmp_path / ".worktrees" / "issue-77"
        target.mkdir(parents=True)
        (target / ".git").write_text("gitdir: /tmp/mock")
        (target / "wrong.txt").write_text("bad scene")

        with patch.object(
            manager.worktree_manager,
            "_find_worktree_for_branch",
            return_value=tmp_path / ".worktrees" / "other-77",
        ):

            def mock_run(cmd, *args, **kwargs):
                if cmd[:3] == ["git", "worktree", "remove"]:
                    import shutil

                    shutil.rmtree(target)
                return CompletedProcess(returncode=0)

            with patch(
                "subprocess.run",
                side_effect=mock_run,
            ) as mock_run:
                path, is_temp = manager._ensure_manager_worktree(77, "task/issue-77")

        assert path == target
        assert is_temp is True
        assert not (target / "wrong.txt").exists()
        assert mock_run.call_args.args[0][:3] == ["git", "worktree", "add"]

    def test_align_auto_scene_to_base_resets_canonical_task_scene(self, tmp_path: Path):
        """Test alignment for fresh branch (no commits) - should reset."""
        config = make_config()
        config.scene_base_ref = "origin/main"
        manager = ManagerExecutor(config, repo_path=tmp_path)

        # Mock git log to return no commits (fresh branch)
        def mock_run_fresh(cmd, *args, **kwargs):
            if cmd[:3] == ["git", "log", "--oneline"]:
                # Fresh branch - log command fails
                return CompletedProcess(returncode=128, stdout="", stderr="error")
            return CompletedProcess(returncode=0)

        with patch(
            "subprocess.run",
            side_effect=mock_run_fresh,
        ) as mock_run:
            ok = manager.worktree_manager.align_auto_scene_to_base(
                tmp_path / ".worktrees" / "issue-77",
                "task/issue-77",
            )

        assert ok is True
        calls = [call.args[0] for call in mock_run.call_args_list]
        # For fresh branch: fetch + full reset
        assert calls == [
            ["git", "log", "--oneline", "-n", "1", "task/issue-77"],
            ["git", "fetch", "--all", "--prune"],
            ["git", "checkout", "task/issue-77"],
            ["git", "reset", "--hard", "origin/main"],
            ["git", "clean", "-fd"],
        ]

    def test_align_auto_scene_preserves_existing_task_branch(self, tmp_path: Path):
        """Test alignment for existing branch with commits - should NOT reset."""
        config = make_config()
        config.scene_base_ref = "origin/main"
        manager = ManagerExecutor(config, repo_path=tmp_path)

        # Mock git log to show branch has commits
        def mock_run_existing(cmd, *args, **kwargs):
            if cmd[:3] == ["git", "log", "--oneline"]:
                # Existing branch with commits
                return CompletedProcess(
                    returncode=0, stdout="abc123 Previous commit\n", stderr=""
                )
            return CompletedProcess(returncode=0)

        with patch(
            "subprocess.run",
            side_effect=mock_run_existing,
        ) as mock_run:
            ok = manager.worktree_manager.align_auto_scene_to_base(
                tmp_path / ".worktrees" / "issue-77",
                "task/issue-77",
            )

        assert ok is True
        calls = [call.args[0] for call in mock_run.call_args_list]
        # For existing branch: only fetch, no destructive operations
        assert calls == [
            ["git", "log", "--oneline", "-n", "1", "task/issue-77"],
            ["git", "fetch", "--all", "--prune"],
        ]

    def test_align_auto_scene_to_base_skips_manual_scene(self, tmp_path: Path):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=tmp_path)

        with patch("subprocess.run") as mock_run:
            ok = manager.worktree_manager.align_auto_scene_to_base(
                tmp_path / ".worktrees" / "manual",
                "dev/issue-999",
            )

        assert ok is True
        mock_run.assert_not_called()


class TestManagerCommandNormalization:
    """Tests for ManagerExecutor command normalization."""

    def test_normalize_manager_command_strips_unsupported_worktree(self):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "vibe3",
            "run",
            "--worktree",
            "Implement issue #1",
        ]

        with patch.object(
            manager.worktree_manager,
            "_supports_run_worktree_option",
            return_value=False,
        ):
            normalized = manager._normalize_manager_command(cmd, Path("/tmp/wt-1"))

        assert "--worktree" not in normalized

    def test_normalize_manager_command_keeps_supported_worktree(self):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "vibe3",
            "run",
            "--worktree",
            "Implement issue #1",
        ]

        with patch.object(
            manager.worktree_manager,
            "_supports_run_worktree_option",
            return_value=True,
        ):
            normalized = manager._normalize_manager_command(cmd, Path("/tmp/wt-1"))

        assert normalized == cmd


class TestManagerDispatchIntegration:
    """Integration tests for full manager dispatch flow with ManagerExecutor."""

    def test_dispatch_manager_executes_in_resolved_manager_cwd(self):
        config = make_config()
        manager = ManagerExecutor(config, dry_run=False, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=102, title="Manager real dispatch")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-102"},
        ):
            with patch.object(
                manager,
                "_resolve_manager_cwd",
                return_value=(Path("/tmp/wt-issue-102"), False),
            ):
                with patch.object(
                    manager.worktree_manager,
                    "align_auto_scene_to_base",
                    return_value=True,
                ):
                    with patch.object(
                        manager, "_normalize_manager_command", return_value=["uv"]
                    ):
                        with patch.object(
                            manager.status_service,
                            "get_active_flow_count",
                            return_value=0,
                        ):
                            with patch.object(
                                manager.result_handler, "update_state_label"
                            ):
                                with patch.object(
                                    manager.flow_manager.store,
                                    "add_event",
                                    return_value=None,
                                ) as mock_add_event:
                                    handle = AsyncExecutionHandle(
                                        tmux_session="vibe3-manager-102",
                                        log_path=Path(
                                            "temp/logs/vibe3-manager-102.async.log"
                                        ),
                                        prompt_file_path=Path("/tmp/prompt.md"),
                                    )
                                    mock_backend = MagicMock()
                                    start_async_command = (
                                        mock_backend.start_async_command
                                    )
                                    start_async_command.return_value = handle
                                    manager._backend = mock_backend
                                    result = manager.dispatch_manager(issue)

        assert result is True
        # Async dispatch only records "dispatched" event, not success/failure
        mock_add_event.assert_called_once()
        assert mock_add_event.call_args.args[1] == "manager_dispatched"
        mock_backend.start_async_command.assert_called_once()
        assert mock_backend.start_async_command.call_args.kwargs["cwd"] == Path(
            "/tmp/wt-issue-102"
        )
