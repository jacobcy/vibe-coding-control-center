"""Tests for Orchestra ManagerExecutor - manager dispatch operations."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


class TestManagerDispatch:
    """Tests for manager dispatch operations."""

    def test_mark_manager_start_failed_marks_flow_stale(self):
        """manager 启动失败时，flow 应被标记为 stale（而不是保持 active）。"""
        config = MagicMock()
        config.max_concurrent_flows = 3
        config.dry_run = False
        config.circuit_breaker.enabled = False

        executor = ManagerExecutor.__new__(ManagerExecutor)
        executor.config = config
        executor.dry_run = False
        executor._queued_issues = set()
        executor._last_error_category = None

        executor.result_handler = MagicMock()
        executor._flow_manager = MagicMock()
        executor._circuit_breaker = None
        executor.status_service = MagicMock()
        executor._registry = MagicMock()
        executor._registry.count_live_worker_sessions.return_value = 0

        # flow exists with a branch
        executor._flow_manager.get_flow_for_issue.return_value = {
            "branch": "task/issue-301",
            "flow_status": "active",
        }

        issue = make_issue(301)
        executor._mark_manager_start_failed(issue, "test failure")

        # flow should be marked stale
        executor._flow_manager.store.update_flow_state.assert_called_once_with(
            "task/issue-301", flow_status="stale"
        )
        # issue should be marked FAILED
        executor.result_handler.update_state_label.assert_called_once_with(
            301, IssueState.FAILED
        )

    def test_dispatch_manager_dry_run_skips_flow_creation_and_execution(self):
        config = OrchestraConfig(dry_run=True)
        manager = ManagerExecutor(config, dry_run=True, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=101, title="Dry run manager dispatch")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
        ) as mock_create_flow:
            manager._registry = MagicMock()
            manager._registry.count_live_worker_sessions.return_value = 0
            with patch("subprocess.run") as mock_run:
                result = manager.dispatch_manager(issue)

        assert result is True
        mock_create_flow.assert_not_called()
        # subprocess.run might be called by other components (e.g. SQLiteClient)
        # but NOT for actual execution if dry_run works.
        # However, ManagerExecutor doesn't call run_command in dry_run mode.
        exec_calls = [c for c in mock_run.call_args_list if "vibe3" in str(c[0][0])]
        assert len(exec_calls) == 0

    def test_dispatch_manager_starts_internal_manager_run_in_target_worktree(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        manager._registry = MagicMock()
        issue = make_issue(number=102, title="Manager session test")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-102"},
        ):
            with patch.object(
                manager._registry, "count_live_worker_sessions", return_value=0
            ):
                with patch.object(
                    manager,
                    "_resolve_manager_cwd",
                    return_value=(Path("/tmp/repo/.worktrees/issue-102"), False),
                ):
                    with patch.object(
                        manager.worktree_manager,
                        "align_auto_scene_to_base",
                        return_value=True,
                    ):
                        with patch.object(manager.result_handler, "update_state_label"):
                            with patch.object(
                                manager.flow_manager.store,
                                "update_flow_state",
                            ):
                                with patch.object(
                                    manager.flow_manager.store,
                                    "add_event",
                                ) as mock_add_event:
                                    with patch.object(
                                        manager._backend,
                                        "start_async_command",
                                        return_value=SimpleNamespace(
                                            tmux_session="vibe3-manager-102",
                                            log_path=Path(
                                                "/tmp/repo/temp/logs/vibe3-manager-102.async.log"
                                            ),
                                        ),
                                    ) as mock_start:
                                        result = manager.dispatch_manager(issue)

        assert result is True
        mock_start.assert_called_once()
        call = mock_start.call_args
        cmd = call.args[0]
        assert cmd[:4] == ["uv", "run", "--project", "/tmp/repo"]
        assert cmd[4:7] == [
            "python",
            "-I",
            str(Path("/tmp/repo/src/vibe3/cli.py").resolve()),
        ]
        assert cmd[7] == "run"
        assert "--manager-issue" in cmd
        assert "--sync" in cmd
        assert call.kwargs["cwd"] == Path("/tmp/repo/.worktrees/issue-102")
        # manager_session_id is no longer written to flow_state
        # (registry is the source of truth)
        # Async dispatch records "dispatched" event, not success
        mock_add_event.assert_called_once()
        assert mock_add_event.call_args.args[1] == "manager_dispatched"

    def test_dispatch_manager_does_not_preclaim_before_launch(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        manager._registry = MagicMock()
        issue = make_issue(number=103, title="Claim before manager run")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-103"},
        ):
            with patch.object(
                manager._registry, "count_live_worker_sessions", return_value=0
            ):
                with patch.object(
                    manager,
                    "_resolve_manager_cwd",
                    return_value=(Path("/tmp/repo/.worktrees/issue-103"), False),
                ):
                    with patch.object(
                        manager.worktree_manager,
                        "align_auto_scene_to_base",
                        return_value=True,
                    ):
                        with patch.object(
                            manager.result_handler, "update_state_label"
                        ) as mock_update:
                            with patch.object(
                                manager.result_handler, "on_dispatch_success"
                            ):
                                with patch.object(
                                    manager._backend,
                                    "start_async_command",
                                    return_value=SimpleNamespace(
                                        tmux_session="vibe3-manager-103",
                                        log_path=Path(
                                            "/tmp/repo/temp/logs/vibe3-manager-103.async.log"
                                        ),
                                    ),
                                ):
                                    result = manager.dispatch_manager(issue)

        assert result is True
        mock_update.assert_not_called()

    def test_dispatch_manager_start_failure_marks_issue_failed(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        manager._registry = MagicMock()
        issue = make_issue(number=104, title="Manager startup failure")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-104"},
        ):
            with patch.object(
                manager._registry, "count_live_worker_sessions", return_value=0
            ):
                with patch.object(
                    manager,
                    "_resolve_manager_cwd",
                    return_value=(Path("/tmp/repo/.worktrees/issue-104"), False),
                ):
                    with patch.object(
                        manager.worktree_manager,
                        "align_auto_scene_to_base",
                        return_value=True,
                    ):
                        with patch.object(
                            manager.result_handler, "update_state_label"
                        ) as mock_update:
                            with patch.object(
                                manager.result_handler, "post_failure_comment"
                            ) as mock_comment:
                                with patch.object(
                                    manager._backend,
                                    "start_async_command",
                                    side_effect=RuntimeError("tmux unavailable"),
                                ):
                                    result = manager.dispatch_manager(issue)

        assert result is False
        assert mock_update.call_args_list[-1].args == (issue.number, IssueState.FAILED)
        mock_comment.assert_called_once()

    def test_dispatch_manager_preserves_temporary_worktree_after_async_launch(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        manager._registry = MagicMock()
        issue = make_issue(number=105, title="Preserve launched worktree")

        with patch.object(
            manager.flow_manager,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-105"},
        ):
            with patch.object(
                manager._registry, "count_live_worker_sessions", return_value=0
            ):
                with patch.object(
                    manager,
                    "_resolve_manager_cwd",
                    return_value=(Path("/tmp/repo/.worktrees/issue-105"), True),
                ):
                    with patch.object(
                        manager.worktree_manager,
                        "align_auto_scene_to_base",
                        return_value=True,
                    ):
                        with patch.object(
                            manager.worktree_manager, "recycle"
                        ) as mock_recycle:
                            with patch.object(
                                manager._backend,
                                "start_async_command",
                                return_value=SimpleNamespace(
                                    tmux_session="vibe3-manager-105",
                                    log_path=Path(
                                        "/tmp/repo/temp/logs/vibe3-manager-105.async.log"
                                    ),
                                ),
                            ):
                                result = manager.dispatch_manager(issue)

        assert result is True
        mock_recycle.assert_not_called()

    def test_dispatch_manager_refuses_launch_when_effective_capacity_is_full(
        self,
    ):
        """dispatch_manager refuses launch when capacity is exhausted."""
        config = OrchestraConfig(max_concurrent_flows=3)
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        manager._registry = MagicMock()
        issue = make_issue(number=42, title="Capacity test")

        with patch.object(
            manager._registry, "count_live_worker_sessions", return_value=3
        ):
            # Effective capacity = max(0, 3 - 3 - 0) = 0
            # Should refuse dispatch
            result = manager.dispatch_manager(issue)

        assert result is False
