"""Tests for flow lifecycle operations."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from vibe3.services.flow_service import FlowService


class TestFlowLifecycle:
    """Tests for flow close behavior."""

    @staticmethod
    def _build_flow_store(
        mock_store: Mock, task_issue_number: int | None = None
    ) -> None:
        mock_store.get_flow_state.return_value = {
            "branch": "task/current-flow",
            "flow_slug": "current_flow",
            "flow_status": "active",
            "task_issue_number": task_issue_number,
            "updated_at": "2026-03-26T00:00:00",
        }

    @patch("vibe3.services.flow_lifecycle.GitClient")
    @patch("vibe3.services.flow_lifecycle.GitHubClient")
    def test_close_flow_closes_bound_task_issue(
        self,
        mock_github_class: MagicMock,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Closing a flow should also close its bound task issue."""
        self._build_flow_store(mock_store, task_issue_number=220)

        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        mock_github_class.return_value.close_issue.assert_called_once_with(220)

    @patch("vibe3.services.flow_lifecycle.GitClient")
    @patch("vibe3.services.flow_lifecycle.GitHubClient")
    def test_close_flow_skips_issue_close_when_no_task_issue(
        self,
        mock_github_class: MagicMock,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Taskless flow close should not attempt to close any issue."""
        self._build_flow_store(mock_store)

        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        mock_github_class.return_value.close_issue.assert_not_called()

    @patch("vibe3.services.flow_lifecycle.GitClient")
    @patch("vibe3.services.flow_lifecycle.GitHubClient")
    def test_close_flow_rejects_unmerged_pr_when_check_enabled(
        self,
        mock_github_class: MagicMock,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Flow with an open PR must not be closed while PR check is enabled."""
        self._build_flow_store(mock_store, task_issue_number=220)
        mock_store.get_flow_state.return_value["pr_number"] = 123

        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []
        mock_github_class.return_value.get_pr.return_value = MagicMock(
            number=123,
            state="OPEN",
            merged_at=None,
        )

        service = FlowService(store=mock_store)

        with pytest.raises(RuntimeError, match="PR #123 is not merged"):
            service.close_flow("task/current-flow", check_pr=True)

        mock_git.delete_branch.assert_not_called()
        mock_git.delete_remote_branch.assert_not_called()
        mock_store.update_flow_state.assert_not_called()

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_switches_off_current_branch_before_delete(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Closing the current worktree branch should switch away before delete."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
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

        mock_store.get_flow_dependents.return_value = []

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

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_switches_to_single_dependent_without_pull(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Single dependent branch should be the switch target without pulling."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
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

        mock_store.get_flow_dependents.return_value = ["task/dependent"]

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert actions.index("switch:task/dependent") < actions.index(
            "delete_local:task/current-flow:True"
        )
        assert not any(action == "run:pull" for action in actions)

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_raises_if_current_branch_cannot_switch_away(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Branch close should fail when target missing."""
        self._build_flow_store(mock_store)

        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.switch_branch.side_effect = RuntimeError("checkout failed")
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        with pytest.raises(
            RuntimeError, match="Cannot switch away from closing branch"
        ):
            service.close_flow("task/current-flow")

        mock_git.delete_branch.assert_not_called()
        mock_store.update_flow_state.assert_not_called()

    @patch("vibe3.services.flow_lifecycle.GitClient")
    def test_close_flow_does_not_pull_if_post_close_switch_fails(
        self,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Post-close switch failure should not pull on an unrelated current branch."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/other"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git.delete_branch.side_effect = lambda branch, force=False: actions.append(
            f"delete_local:{branch}:{force}"
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git.switch_branch.side_effect = RuntimeError("checkout failed")
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git

        mock_store.get_flow_dependents.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert "delete_local:task/current-flow:True" in actions
        assert not any(action == "run:pull" for action in actions)
