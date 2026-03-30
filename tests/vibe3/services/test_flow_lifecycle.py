"""Tests for flow lifecycle operations."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from vibe3.models.pr import PRResponse, PRState
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

    @patch("vibe3.services.flow_lifecycle.GitClient")
    @patch("vibe3.services.flow_lifecycle.GitHubClient")
    @patch("vibe3.services.flow_lifecycle.sync_flow_done_task_labels")
    def test_close_flow_switches_off_current_branch_before_delete(
        self,
        mock_sync_done_labels: MagicMock,
        mock_gh_class: MagicMock,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Closing the current worktree branch should switch away before delete."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.get_worktree_root.return_value = "/repo/main"
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
        mock_gh = MagicMock()
        mock_gh.get_pr.return_value = PRResponse(
            number=284,
            title="test",
            body="",
            state=PRState.MERGED,
            head_branch="task/current-flow",
            base_branch="main",
            url="https://example.com/pr/284",
            merged_at=None,
        )
        mock_gh_class.return_value = mock_gh

        mock_store.get_flow_dependents.return_value = []
        mock_store.get_issue_links.return_value = [
            {"issue_number": 220, "issue_role": "task"},
            {"issue_number": 221, "issue_role": "related"},
        ]

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert actions.index("switch:main") < actions.index(
            "delete_local:task/current-flow:True"
        )
        mock_store.update_flow_state.assert_called_once_with(
            "task/current-flow",
            flow_status="done",
            latest_actor="workflow",
        )
        mock_store.add_event.assert_called_once_with(
            "task/current-flow",
            "flow_closed",
            "workflow",
            "Flow closed, branch 'task/current-flow' deleted",
        )
        mock_sync_done_labels.assert_called_once_with(mock_store, "task/current-flow")

    @patch("vibe3.services.flow_lifecycle.GitClient")
    @patch("vibe3.services.flow_lifecycle.GitHubClient")
    @patch("vibe3.services.flow_lifecycle.sync_flow_done_task_labels")
    def test_close_flow_switches_to_single_dependent_without_pull(
        self,
        _mock_sync_done_labels: MagicMock,
        mock_gh_class: MagicMock,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Single dependent branch should be the switch target without pulling."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.get_worktree_root.return_value = "/repo/wt-codex"
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
        mock_gh = MagicMock()
        mock_gh.get_pr.return_value = PRResponse(
            number=284,
            title="test",
            body="",
            state=PRState.MERGED,
            head_branch="task/current-flow",
            base_branch="main",
            url="https://example.com/pr/284",
            merged_at=None,
        )
        mock_gh_class.return_value = mock_gh

        mock_store.get_flow_dependents.return_value = ["task/dependent"]
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert actions.index("switch:task/dependent") < actions.index(
            "delete_local:task/current-flow:True"
        )
        assert not any(action.startswith("run:pull") for action in actions)

    @patch("vibe3.services.flow_lifecycle.GitClient")
    @patch("vibe3.services.flow_lifecycle.GitHubClient")
    @patch("vibe3.services.flow_lifecycle.sync_flow_done_task_labels")
    def test_close_flow_raises_if_current_branch_cannot_switch_away(
        self,
        _mock_sync_done_labels: MagicMock,
        mock_gh_class: MagicMock,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Branch close should fail when target missing."""
        self._build_flow_store(mock_store)

        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/current-flow"
        mock_git.get_worktree_root.return_value = "/repo/wt-codex"
        mock_git.switch_branch.side_effect = RuntimeError("checkout failed")
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git_class.return_value = mock_git
        mock_gh = MagicMock()
        mock_gh.get_pr.return_value = PRResponse(
            number=284,
            title="test",
            body="",
            state=PRState.MERGED,
            head_branch="task/current-flow",
            base_branch="main",
            url="https://example.com/pr/284",
            merged_at=None,
        )
        mock_gh_class.return_value = mock_gh

        mock_store.get_flow_dependents.return_value = []
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store)

        with pytest.raises(
            RuntimeError, match="Cannot switch away from closing branch"
        ):
            service.close_flow("task/current-flow")

        mock_git.delete_branch.assert_not_called()
        mock_store.update_flow_state.assert_not_called()

    @patch("vibe3.services.flow_lifecycle.GitClient")
    @patch("vibe3.services.flow_lifecycle.GitHubClient")
    @patch("vibe3.services.flow_lifecycle.sync_flow_done_task_labels")
    def test_close_flow_does_not_pull_if_post_close_switch_fails(
        self,
        _mock_sync_done_labels: MagicMock,
        mock_gh_class: MagicMock,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """Post-close switch failure should not pull on an unrelated current branch."""
        self._build_flow_store(mock_store)

        actions: list[str] = []
        mock_git = MagicMock()
        mock_git.get_current_branch.return_value = "task/other"
        mock_git.get_worktree_root.return_value = "/repo/wt-codex"
        mock_git.branch_exists.return_value = True
        mock_git.is_branch_occupied_by_worktree.return_value = False
        mock_git.delete_branch.side_effect = (
            lambda branch, force=False, skip_if_worktree=False: actions.append(
                f"delete_local:{branch}:{force}"
            )
        )
        mock_git.delete_remote_branch.side_effect = lambda branch: actions.append(
            f"delete_remote:{branch}"
        )
        mock_git.switch_branch.side_effect = RuntimeError("checkout failed")
        mock_git._run.side_effect = lambda args: actions.append(f"run:{' '.join(args)}")
        mock_git_class.return_value = mock_git
        mock_gh = MagicMock()
        mock_gh.get_pr.return_value = PRResponse(
            number=284,
            title="test",
            body="",
            state=PRState.MERGED,
            head_branch="task/current-flow",
            base_branch="main",
            url="https://example.com/pr/284",
            merged_at=None,
        )
        mock_gh_class.return_value = mock_gh

        mock_store.get_flow_dependents.return_value = []
        mock_store.get_issue_links.return_value = []

        service = FlowService(store=mock_store)

        service.close_flow("task/current-flow")

        assert "delete_local:task/current-flow:True" in actions
        assert not any(action.startswith("run:pull") for action in actions)

    @patch("vibe3.services.flow_lifecycle.GitClient")
    @patch("vibe3.services.flow_lifecycle.GitHubClient")
    @patch("vibe3.services.flow_lifecycle.sync_flow_done_task_labels")
    def test_close_flow_rejects_when_pr_not_merged(
        self,
        _mock_sync_done_labels: MagicMock,
        mock_gh_class: MagicMock,
        mock_git_class: MagicMock,
        mock_store: Mock,
    ) -> None:
        """flow done should reject when PR is not merged."""
        self._build_flow_store(mock_store)
        mock_git_class.return_value = MagicMock()
        mock_gh = MagicMock()
        mock_gh.get_pr.return_value = PRResponse(
            number=284,
            title="test",
            body="",
            state=PRState.OPEN,
            head_branch="task/current-flow",
            base_branch="main",
            url="https://example.com/pr/284",
            merged_at=None,
        )
        mock_gh_class.return_value = mock_gh

        service = FlowService(store=mock_store)

        with pytest.raises(Exception, match="尚未 merged"):
            service.close_flow("task/current-flow")

        mock_store.update_flow_state.assert_not_called()

    @patch("vibe3.services.flow_lifecycle.sync_flow_blocked_task_label")
    def test_block_flow_syncs_task_issue_blocked_label(
        self,
        mock_sync_blocked_label: MagicMock,
        mock_store: Mock,
    ) -> None:
        mock_store.get_flow_state.return_value = {
            "branch": "task/current-flow",
            "flow_slug": "current_flow",
            "flow_status": "active",
        }
        service = FlowService(store=mock_store)

        service.block_flow("task/current-flow", reason="waiting")

        mock_sync_blocked_label.assert_called_once_with(mock_store, "task/current-flow")
