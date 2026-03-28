"""Tests for Task management functionality."""

from vibe3.models.flow import FlowState
from vibe3.services.task_service import TaskService


class TestTaskRetrieval:
    """Tests for retrieving task details."""

    def test_get_task_success(self, mock_store) -> None:
        """Test getting task details."""
        mock_store.get_flow_state.return_value = {
            "branch": "test-branch",
            "flow_slug": "test-flow",
            "flow_status": "active",
            "task_issue_number": 101,
            "next_step": "Complete tests",
            "updated_at": "2026-03-16T00:00:00",
        }

        service = TaskService(store=mock_store)
        result = service.get_task("test-branch")

        assert result is not None
        assert isinstance(result, FlowState)
        assert result.flow_slug == "test-flow"
        assert result.task_issue_number == 101
        assert result.next_step == "Complete tests"

    def test_get_task_not_found(self, mock_store) -> None:
        """Test getting task when not found."""
        mock_store.get_flow_state.return_value = None

        service = TaskService(store=mock_store)
        result = service.get_task("nonexistent-branch")

        assert result is None
