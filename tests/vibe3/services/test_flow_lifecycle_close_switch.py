"""Tests for flow close branch switching behavior."""

from unittest.mock import MagicMock, Mock, call, patch

from vibe3.services.flow_service import FlowService


class TestFlowCloseBranchSwitching:
    """Tests for closing a flow and switching away from the branch."""

    @staticmethod
    def _build_flow_store(mock_store: Mock) -> None:
        mock_store.get_flow_state.return_value = {
            "branch": "task/current-flow",
            "flow_slug": "current_flow",
            "flow_status": "active",
            "updated_at": "2026-03-26T00:00:00",
        }

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_uses_safe_branch_on_dependency_lookup_failure(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Dependency lookup failure should avoid main on non-baseline worktrees."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.get_worktree_root.return_value = "/repo/.worktrees/wt-codex"
        mock_git.get_safe_main_branch_name.return_value = "vibe/main-safe/wt-codex"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git.switch_branch.side_effect = lambda branch: actions.append(
            f"switch:{branch}"
        )
        mock_git.delete_branch.side_effect = (
            lambda branch, force=False, skip_if_worktree=False: actions.append(
                f"delete_local:{branch}:{force}"
            )
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.side_effect = RuntimeError("db unavailable")

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow", check_pr=False)

        assert actions.index("switch:vibe/main-safe/wt-codex") < actions.index(
            "delete_local:task/current-flow:True"
        )
        assert not any(action.startswith("run:pull") for action in actions)
        mock_git.get_safe_main_branch_name.assert_called_once()
        mock_store.get_flow_dependents.assert_called_once_with("task/current-flow")
        mock_store.update_flow_state.assert_called_once_with(
            "task/current-flow",
            flow_status="done",
            latest_actor="workflow",
        )

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_switches_to_safe_branch_when_main_is_occupied(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """If main is occupied, close flow should move to a worktree-safe branch."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.get_worktree_root.return_value = "/repo/main"
        mock_git.branch_exists.side_effect = (
            lambda branch: branch == "task/current-flow"
        )
        mock_git.is_branch_occupied_by_worktree.side_effect = (
            lambda branch: branch == "main"
        )
        mock_git.get_safe_main_branch_name.return_value = (
            "vibe/main-safe/wt-feature-handoff"
        )
        mock_git.create_branch.side_effect = (
            lambda branch, start_ref="origin/main": actions.append(
                f"create:{branch}:{start_ref}"
            )
        )
        mock_git.delete_branch.side_effect = (
            lambda branch, force=False, skip_if_worktree=False: actions.append(
                f"delete_local:{branch}:{force}"
            )
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow", check_pr=False)

        assert actions.index(
            "create:vibe/main-safe/wt-feature-handoff:origin/main"
        ) < actions.index("delete_local:task/current-flow:True")
        assert not any(action.startswith("run:pull") for action in actions)
        mock_git.is_branch_occupied_by_worktree.assert_has_calls(
            [
                call("main"),
                call("task/current-flow"),
            ]
        )
        mock_git.get_safe_main_branch_name.assert_called_once()

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_uses_safe_branch_when_main_is_occupied_on_post_close(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Closing another branch should still avoid switching to occupied main."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/other"
        mock_git.get_worktree_root.return_value = "/repo/main"
        mock_git.branch_exists.side_effect = (
            lambda branch: branch == "task/current-flow"
        )
        mock_git.is_branch_occupied_by_worktree.return_value = True
        mock_git.get_safe_main_branch_name.return_value = (
            "vibe/main-safe/wt-feature-handoff"
        )
        mock_git.create_branch.side_effect = (
            lambda branch, start_ref="origin/main": actions.append(
                f"create:{branch}:{start_ref}"
            )
        )
        mock_git.delete_branch.side_effect = (
            lambda branch, force=False, skip_if_worktree=False: actions.append(
                f"delete_local:{branch}:{force}"
            )
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow", check_pr=False)

        assert "create:vibe/main-safe/wt-feature-handoff:origin/main" in actions
        assert "switch:main" not in actions
        assert not any(action.startswith("run:pull") for action in actions)

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_skips_local_delete_when_branch_is_occupied_by_other_worktree(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Closing a branch checked out elsewhere should skip local deletion."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.get_worktree_root.return_value = "/repo/main"
        mock_git.branch_exists.side_effect = (
            lambda branch: branch == "task/current-flow"
        )
        mock_git.is_branch_occupied_by_worktree.side_effect = (
            lambda branch: branch == "task/current-flow"
        )
        mock_git.create_branch.side_effect = (
            lambda branch, start_ref="origin/main": actions.append(
                f"create:{branch}:{start_ref}"
            )
        )
        mock_git.switch_branch.side_effect = lambda branch: actions.append(
            f"switch:{branch}"
        )
        mock_git.delete_branch.side_effect = (
            lambda branch, force=False, skip_if_worktree=False: actions.append(
                f"delete_local:{branch}:{force}"
            )
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow", check_pr=False)

        assert "create:main:origin/main" in actions
        assert not any(action.startswith("delete_local:") for action in actions)
        assert "delete_remote:task/current-flow" in actions

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_delegates_worktree_race_to_delete_branch(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Race condition handling is delegated to GitClient.delete_branch."""
        self._build_flow_store(mock_store)

        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.get_worktree_root.return_value = "/repo/main"
        mock_git.branch_exists.side_effect = lambda branch: branch in {
            "task/current-flow",
            "main",
        }
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow", check_pr=False)

        mock_git.delete_branch.assert_called_once_with(
            "task/current-flow", force=True, skip_if_worktree=True
        )

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_returns_to_develop_branch_in_develop_worktree(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Develop worktree should restore to develop and sync origin/main."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.get_worktree_root.return_value = "/repo/develop"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git.switch_branch.side_effect = lambda branch: actions.append(
            f"switch:{branch}"
        )
        mock_git.delete_branch.side_effect = (
            lambda branch, force=False, skip_if_worktree=False: actions.append(
                f"delete_local:{branch}:{force}"
            )
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow", check_pr=False)

        assert actions.index("switch:develop") < actions.index(
            "delete_local:task/current-flow:True"
        )
        assert "run:pull origin develop" in actions
