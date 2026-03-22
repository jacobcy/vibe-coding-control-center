"""Tests for Flow binding functionality (via TaskService.link_issue)."""

from vibe3.models.flow import IssueLink
from vibe3.services.task_service import TaskService


class TestFlowBinding:
    """Tests for binding tasks to flows via TaskService."""

    def test_bind_flow_success(self, mock_store) -> None:
        """Test binding a task issue to a flow via TaskService.link_issue."""
        service = TaskService(store=mock_store)
        result = service.link_issue(
            branch="test-branch",
            issue_number=123,
            role="task",
            actor="test-actor",
        )

        assert isinstance(result, IssueLink)
        assert result.issue_number == 123
        assert result.issue_role == "task"

        mock_store.add_issue_link.assert_called_once_with("test-branch", 123, "task")
        mock_store.update_flow_state.assert_called_once_with(
            "test-branch",
            task_issue_number=123,
            latest_actor="test-actor",
        )
        mock_store.add_event.assert_called_once_with(
            "test-branch",
            "issue_linked",
            "test-actor",
            "Issue #123 linked as task",
        )

    def test_bind_flow_already_bound(self, mock_store) -> None:
        """Binding again overwrites — link_issue is idempotent at store level."""
        service = TaskService(store=mock_store)
        result = service.link_issue(
            branch="test-branch",
            issue_number=456,
            role="task",
            actor="test-actor",
        )

        assert isinstance(result, IssueLink)
        assert result.issue_number == 456
