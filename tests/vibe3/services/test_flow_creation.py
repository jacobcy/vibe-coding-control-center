"""Tests for Flow creation functionality."""

from unittest.mock import Mock

import pytest

from vibe3.models.flow import FlowState
from vibe3.services.flow_service import FlowService


class TestFlowCreation:
    """Tests for creating flows."""

    def test_create_flow_success(self, mock_store) -> None:
        """Test creating a flow successfully."""
        service = FlowService(store=mock_store)
        result = service.create_flow(
            slug="test-flow",
            branch="test-branch",
        )

        assert isinstance(result, FlowState)
        assert result.flow_slug == "test-flow"
        assert result.branch == "test-branch"
        assert result.flow_status == "active"

        mock_store.update_flow_state.assert_called_once_with(
            "test-branch",
            flow_slug="test-flow",
            latest_actor="workflow",
        )
        mock_store.add_event.assert_called_once_with(
            "test-branch",
            "flow_created",
            "workflow",
            "Flow 'test-flow' created",
        )

    def test_create_flow_no_task_id(self, mock_store) -> None:
        """create_flow no longer accepts task_id; binding via TaskService."""
        service = FlowService(store=mock_store)
        result = service.create_flow(
            slug="test-flow",
            branch="test-branch",
        )

        assert result.flow_slug == "test-flow"
        # No add_issue_link call — task binding is separate
        mock_store.add_issue_link.assert_not_called()

    def test_create_flow_with_branch_rejects_dirty_worktree(self) -> None:
        """create_flow_with_branch should fail fast when worktree is dirty."""
        mock_store = Mock()
        mock_git = Mock()
        mock_git.branch_exists.return_value = False
        mock_git.has_uncommitted_changes.return_value = True

        service = FlowService(store=mock_store, git_client=mock_git)

        with pytest.raises(RuntimeError, match="Worktree has uncommitted changes"):
            service.create_flow_with_branch("demo")

        mock_git.create_branch.assert_not_called()

    def test_create_flow_with_branch_checks_dirty_once(self) -> None:
        """create_flow_with_branch should not duplicate dirty checks."""
        mock_store = Mock()
        mock_store.get_flow_state.return_value = {
            "branch": "task/demo",
            "flow_slug": "demo",
            "flow_status": "active",
            "updated_at": "2026-03-16T00:00:00",
        }
        mock_git = Mock()
        mock_git.branch_exists.return_value = False
        mock_git.has_uncommitted_changes.return_value = False

        service = FlowService(store=mock_store, git_client=mock_git)
        result = service.create_flow_with_branch("demo")

        assert result.flow_slug == "demo"
        mock_git.has_uncommitted_changes.assert_called_once()
        mock_git.create_branch.assert_called_once_with("task/demo", "origin/main")
