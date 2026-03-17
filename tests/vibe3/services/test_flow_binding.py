"""Tests for Flow binding functionality."""

from vibe3.models.flow import FlowState
from vibe3.services.flow_service import FlowService


class TestFlowBinding:
    """Tests for binding tasks to flows."""

    def test_bind_flow_success(self, mock_store) -> None:
        """Test binding a task to a flow."""
        service = FlowService(store=mock_store)
        result = service.bind_flow(
            branch="test-branch",
            task_id="TASK-123",
            actor="test-actor",
        )

        assert isinstance(result, FlowState)
        assert result.flow_slug == "test-flow"

        # Verify store calls
        mock_store.update_flow_state.assert_called_once_with(
            "test-branch",
            task_issue_number=123,
            latest_actor="test-actor",
        )
        mock_store.add_issue_link.assert_called_once_with("test-branch", 123, "task")
        mock_store.add_event.assert_called_once_with(
            "test-branch",
            "task_bound",
            "test-actor",
            "Task 'TASK-123' bound",
        )

    def test_bind_flow_already_bound(self, mock_store_with_task) -> None:
        """Test binding when a task is already bound."""
        service = FlowService(store=mock_store_with_task)
        # Should handle gracefully or update existing binding
        result = service.bind_flow(
            branch="test-branch",
            task_id="TASK-456",
            actor="test-actor",
        )

        assert result.task_issue_number == 101  # Original task
