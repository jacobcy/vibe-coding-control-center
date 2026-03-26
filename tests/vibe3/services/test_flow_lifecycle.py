"""Tests for flow lifecycle operations."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from vibe3.services.flow_service import FlowService


class TestFlowLifecycle:
    """Tests for flow close behavior."""

    @staticmethod
    def _build_flow_store(mock_store: Mock) -> None:
        mock_store.get_flow_state.return_value = {
            "branch": "task/current-flow",
            "flow_slug": "current_flow",
            "flow_status": "active",
            "updated_at": "2026-03-26T00:00:00",
        }

    @patch("vibe3.services.flow_lifecycle.SQLiteClient")
    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_switches_off_current_branch_before_delete(
        self,
        mock_git_class: MagicMock,
        mock_sqlite_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Closing the current worktree branch should switch away before delete."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.switch_branch.side_effect = lambda branch: actions.append(
            f"switch:{branch}"
        )
        mock_git.delete_branch.side_effect = lambda branch, force=False: actions.append(
            f"delete_local:{branch}:{force}"
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_dependency_store = MagicMock()
        mock_dependency_store.get_flow_dependents.return_value = []
        mock_sqlite_class.return_value = mock_dependency_store

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert actions.index("switch:main") < actions.index(
            "delete_local:task/current-flow:True"
        )
        mock_store.update_flow_state.assert_called_once_with(
            "task/current-flow",
            flow_status="done",
        )
        mock_store.add_event.assert_called_once_with(
            "task/current-flow",
            "flow_closed",
            "system",
            "Flow closed, branch 'task/current-flow' deleted",
        )

    @patch("vibe3.services.flow_lifecycle.SQLiteClient")
    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_switches_to_single_dependent_without_pull(
        self,
        mock_git_class: MagicMock,
        mock_sqlite_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Single dependent branch should be the switch target without pulling."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.switch_branch.side_effect = lambda branch: actions.append(
            f"switch:{branch}"
        )
        mock_git.delete_branch.side_effect = lambda branch, force=False: actions.append(
            f"delete_local:{branch}:{force}"
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_dependency_store = MagicMock()
        mock_dependency_store.get_flow_dependents.return_value = ["task/dependent"]
        mock_sqlite_class.return_value = mock_dependency_store

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert actions.index("switch:task/dependent") < actions.index(
            "delete_local:task/current-flow:True"
        )
        assert not any(action == "run:pull" for action in actions)

    @patch("vibe3.services.flow_lifecycle.SQLiteClient")
    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_raises_if_current_branch_cannot_switch_away(
        self,
        mock_git_class: MagicMock,
        mock_sqlite_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Current branch close should fail clearly when switch target is unavailable."""
        self._build_flow_store(mock_store)

        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.switch_branch.side_effect = RuntimeError("checkout failed")
        mock_git_class.return_value = mock_git

        mock_dependency_store = MagicMock()
        mock_dependency_store.get_flow_dependents.return_value = []
        mock_sqlite_class.return_value = mock_dependency_store

        service = FlowService(store=mock_store)

        with pytest.raises(RuntimeError, match="Cannot switch away from closing branch"):
            service.close_flow("task/current-flow")

        mock_git.delete_branch.assert_not_called()
        mock_store.update_flow_state.assert_not_called()

    @patch("vibe3.services.flow_lifecycle.SQLiteClient")
    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_does_not_pull_if_post_close_switch_fails(
        self,
        mock_git_class: MagicMock,
        mock_sqlite_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Post-close switch failure should not pull on an unrelated current branch."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/other"
        mock_git.branch_exists.return_value = True
        mock_git.delete_branch.side_effect = lambda branch, force=False: actions.append(
            f"delete_local:{branch}:{force}"
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git.switch_branch.side_effect = RuntimeError("checkout failed")
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_dependency_store = MagicMock()
        mock_dependency_store.get_flow_dependents.return_value = []
        mock_sqlite_class.return_value = mock_dependency_store

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert "delete_local:task/current-flow:True" in actions
        assert not any(action == "run:pull" for action in actions)

    @patch("vibe3.services.flow_lifecycle.SQLiteClient")
    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_falls_back_to_main_when_dependency_lookup_fails(
        self,
        mock_git_class: MagicMock,
        mock_sqlite_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Dependency lookup failure should still close flow via main fallback."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.switch_branch.side_effect = lambda branch: actions.append(
            f"switch:{branch}"
        )
        mock_git.delete_branch.side_effect = lambda branch, force=False: actions.append(
            f"delete_local:{branch}:{force}"
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_dependency_store = MagicMock()
        mock_dependency_store.get_flow_dependents.side_effect = RuntimeError(
            "db unavailable"
        )
        mock_sqlite_class.return_value = mock_dependency_store

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert actions.index("switch:main") < actions.index(
            "delete_local:task/current-flow:True"
        )
        assert "run:pull" in actions
        mock_dependency_store.get_flow_dependents.assert_called_once_with(
            "task/current-flow"
        )
        mock_store.update_flow_state.assert_called_once_with(
            "task/current-flow",
            flow_status="done",
        )