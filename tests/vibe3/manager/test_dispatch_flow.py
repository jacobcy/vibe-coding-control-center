"""Tests for orchestra manager dispatch flow, locking and worktree management."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.backends.codeagent import AsyncExecutionHandle
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.READY,
        labels=["state/ready"],
    )


def make_config() -> OrchestraConfig:
    return OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid"))


@pytest.fixture(autouse=True)
def mock_failed_gate():
    """Patch FailedGate to always pass by default in tests."""
    with patch("vibe3.orchestra.failed_gate.FailedGate.check") as mock_check:
        mock_check.return_value = MagicMock(blocked=False)
        yield mock_check


class TestManagerDispatchConcurrency:
    """Tests for concurrent dispatch protection."""

    def test_dispatch_manager_acquires_global_lock(self):
        """Verify that dispatch_manager uses _active_dispatch_locks
        to prevent re-entry.
        """
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        manager._registry = MagicMock(spec=SessionRegistryService)
        manager._registry.count_live_worker_sessions.return_value = 0

        issue = make_issue(123)

        # Simulate a slow dispatch by making _dispatch_manager_impl check the lock
        def slow_impl(iss):
            assert iss.number in manager._active_dispatch_locks
            # While this is running, a second call should fail
            assert manager.dispatch_manager(iss) is False
            return True

        with patch.object(manager, "_dispatch_manager_impl", side_effect=slow_impl):
            result = manager.dispatch_manager(issue)
            assert result is True

        # Lock should be released after completion
        assert 123 not in manager._active_dispatch_locks


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


class TestManagerDispatchIntegration:
    """Integration tests for full manager dispatch flow with ManagerExecutor."""

    def test_dispatch_manager_executes_in_resolved_manager_cwd(self):
        config = make_config()
        manager = ManagerExecutor(config, dry_run=False, repo_path=Path("/tmp/repo"))
        manager._registry = MagicMock()
        manager._registry.count_live_worker_sessions.return_value = 0
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
                    with patch.object(manager.result_handler, "update_state_label"):
                        with patch.object(
                            manager.flow_manager.store,
                            "add_event",
                            return_value=None,
                        ) as mock_add_event:
                            handle = AsyncExecutionHandle(
                                tmux_session="vibe3-manager-102",
                                log_path=Path("temp/logs/vibe3-manager-102.async.log"),
                                prompt_file_path=Path("/tmp/prompt.md"),
                            )
                            mock_backend = MagicMock()
                            start_async_command = mock_backend.start_async_command
                            start_async_command.return_value = handle
                            manager._backend = mock_backend

                            # Mock agent options resolution
                            with patch(
                                "vibe3.runtime.agent_resolver.resolve_manager_agent_options"
                            ) as mock_resolve:
                                mock_resolve.return_value = MagicMock(
                                    backend="claude", model=None
                                )
                                result = manager.dispatch_manager(issue)

        assert result is True
        # Async dispatch only records "dispatched" event, not success/failure
        mock_add_event.assert_called_once()
        assert mock_add_event.call_args.args[1] == "manager_dispatched"
        mock_backend.start_async_command.assert_called_once()
        assert mock_backend.start_async_command.call_args.kwargs["cwd"] == Path(
            "/tmp/wt-issue-102"
        )
