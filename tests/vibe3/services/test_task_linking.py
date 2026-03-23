"""Tests for Task issue linking functionality."""

from vibe3.models.flow import IssueLink
from vibe3.services.task_service import TaskService


class TestIssueLinking:
    """Tests for linking issues to tasks."""

    def test_link_issue_related_role(self, mock_store_for_task) -> None:
        """Test linking an issue with 'related' role."""
        service = TaskService(store=mock_store_for_task)
        result = service.link_issue(
            branch="test-branch",
            issue_number=101,
            role="related",
        )

        assert isinstance(result, IssueLink)
        assert result.branch == "test-branch"
        assert result.issue_number == 101
        assert result.issue_role == "related"

        # Verify store calls
        mock_store_for_task.add_issue_link.assert_called_once_with(
            "test-branch", 101, "related"
        )
        mock_store_for_task.update_flow_state.assert_not_called()
        mock_store_for_task.add_event.assert_called_once()

    def test_link_issue_dependency_role(self, mock_store_for_task) -> None:
        """Test linking an issue with 'dependency' role."""
        service = TaskService(store=mock_store_for_task)
        result = service.link_issue(
            branch="test-branch",
            issue_number=103,
            role="dependency",
        )

        assert isinstance(result, IssueLink)
        assert result.issue_number == 103
        assert result.issue_role == "dependency"

        mock_store_for_task.add_issue_link.assert_called_once_with(
            "test-branch", 103, "dependency"
        )
        mock_store_for_task.update_flow_state.assert_not_called()
        mock_store_for_task.add_event.assert_called_once()

    def test_link_issue_task_role(self, mock_store_for_task) -> None:
        """Test linking an issue with 'task' role."""
        service = TaskService(store=mock_store_for_task)
        result = service.link_issue(
            branch="test-branch",
            issue_number=102,
            role="task",
        )

        assert isinstance(result, IssueLink)
        assert result.issue_number == 102
        assert result.issue_role == "task"

        # Verify store calls - task role should update flow_state
        mock_store_for_task.add_issue_link.assert_called_once_with(
            "test-branch", 102, "task"
        )
        mock_store_for_task.update_flow_state.assert_called_once_with(
            "test-branch",
            task_issue_number=102,
        )
        mock_store_for_task.add_event.assert_called_once()

    def test_link_issue_duplicate_handled(self, mock_store_for_task) -> None:
        """Test handling duplicate issue link."""
        # Store should handle unique constraint gracefully
        service = TaskService(store=mock_store_for_task)

        # First link
        service.link_issue(
            branch="test-branch",
            issue_number=101,
            role="related",
        )

        # Attempt duplicate - should handle gracefully
        # (implementation dependent: either ignore or raise)
        service.link_issue(
            branch="test-branch",
            issue_number=101,
            role="related",
        )

        # Verify both calls were made
        assert mock_store_for_task.add_issue_link.call_count == 2
