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
            path, is_temp = manager._ensure_manager_worktree(77, "task/issue-77")

        assert path == tmp_path / ".worktrees" / "issue-77"
        assert is_temp is True
        assert mock_run.call_args.args[0][:3] == ["git", "worktree", "add"]
        assert mock_run.call_args.kwargs["cwd"] == tmp_path

    def test_ensure_manager_worktree_skips_when_path_exists(self, tmp_path: Path):
        config = make_config()
        manager = ManagerExecutor(config, repo_path=tmp_path)
        existing = tmp_path / ".worktrees" / "issue-77"
        existing.mkdir(parents=True)

        with patch("subprocess.run") as mock_run:
            result = manager._ensure_manager_worktree(77, "task/issue-77")

        assert result == (None, False)
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
                    manager, "_normalize_manager_command", return_value=["uv"]
                ):
                    with patch.object(
                        manager.status_service,
                        "get_active_flow_count",
                        return_value=0,
                    ):
                        with patch.object(
                            manager.result_handler,
                            "record_dispatch_event",
                            return_value=None,
                        ) as mock_record_event:
                            with patch.object(
                                manager.flow_manager,
                                "get_pr_for_issue",
                                return_value=None,
                            ):
                                with patch.object(
                                    manager.result_handler, "update_state_label"
                                ):
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
        mock_record_event.assert_called_once_with(
            "task/issue-102",
            success=True,
            issue_number=102,
            pr_number=None,
        )
        mock_backend.start_async_command.assert_called_once()
        assert mock_backend.start_async_command.call_args.kwargs["cwd"] == Path(
            "/tmp/wt-issue-102"
        )
