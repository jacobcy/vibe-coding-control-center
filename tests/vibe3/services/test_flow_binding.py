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
        )

        assert isinstance(result, IssueLink)
        assert result.issue_number == 123
        assert result.issue_role == "task"

        mock_store.add_issue_link.assert_called_once_with("test-branch", 123, "task")
        mock_store.update_flow_state.assert_called_once_with(
            "test-branch",
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
        )

        assert isinstance(result, IssueLink)
        assert result.issue_number == 456

    def test_bind_related_role(self, mock_store) -> None:
        """Related role should remain local-only."""
        service = TaskService(store=mock_store)

        result = service.link_issue("test-branch", 219, "related")

        assert result.issue_role == "related"
        mock_store.add_issue_link.assert_called_once_with("test-branch", 219, "related")

    def test_reclassify_issue_role(self, mock_store) -> None:
        """Existing issue link can be reclassified without deleting the flow."""
        mock_store.update_issue_link_role.return_value = True
        service = TaskService(store=mock_store)

        result = service.reclassify_issue(
            "debug/vibe-server-fix",
            467,
            old_role="task",
            new_role="related",
        )

        assert result.issue_role == "related"
        mock_store.update_issue_link_role.assert_called_once_with(
            "debug/vibe-server-fix",
            467,
            "task",
            "related",
        )
        mock_store.update_flow_state.assert_called_once_with(
            "debug/vibe-server-fix",
            latest_actor="test-actor",
        )
        mock_store.add_event.assert_called_once_with(
            "debug/vibe-server-fix",
            "issue_reclassified",
            "test-actor",
            "Issue #467 reclassified: task -> related",
        )
