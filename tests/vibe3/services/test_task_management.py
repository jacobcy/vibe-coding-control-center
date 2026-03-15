"""Tests for Task management functionality."""
import pytest
from vibe3.services.task_service import TaskService
from vibe3.models.flow import FlowState


class TestTaskStatus:
    """Tests for task status management."""

    def test_update_task_status_success(self, mock_store) -> None:
        """Test updating task status."""
        # Configure mock to return updated state
        updated_state = {
            "branch": "test-branch",
            "flow_slug": "test-flow",
            "flow_status": "idle",  # This is the updated status
            "task_issue_number": None,
            "next_step": None,
            "updated_at": "2026-03-16T00:00:00",
        }
        mock_store.get_flow_state.return_value = updated_state

        service = TaskService(store=mock_store)
        result = service.update_task_status(
            branch="test-branch",
            status="idle",
            actor="test-actor",
        )

        assert isinstance(result, FlowState)
        assert result.flow_status == "idle"

        # Verify store calls
        mock_store.update_flow_state.assert_called_once_with(
            "test-branch",
            flow_status="idle",
            latest_actor="test-actor",
        )
        mock_store.add_event.assert_called_once()

    def test_update_task_status_flow_not_found(self, mock_store) -> None:
        """Test updating task status when flow not found."""
        mock_store.get_flow_state.return_value = None

        service = TaskService(store=mock_store)
        with pytest.raises(RuntimeError, match="Flow not found"):
            service.update_task_status(
                branch="nonexistent-branch",
                status="idle",
                actor="test-actor",
            )


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


class TestNextStep:
    """Tests for managing next steps."""

    def test_set_next_step_success(self, mock_store) -> None:
        """Test setting next step for a task."""
        # Configure mock to return state with next_step
        updated_state = {
            "branch": "test-branch",
            "flow_slug": "test-flow",
            "flow_status": "active",
            "task_issue_number": None,
            "next_step": "Write tests",  # This is the updated next_step
            "updated_at": "2026-03-16T00:00:00",
        }
        mock_store.get_flow_state.return_value = updated_state

        service = TaskService(store=mock_store)
        result = service.set_next_step(
            branch="test-branch",
            next_step="Write tests",
            actor="test-actor",
        )

        assert isinstance(result, FlowState)
        assert result.next_step == "Write tests"

        # Verify store calls
        mock_store.update_flow_state.assert_called_once_with(
            "test-branch",
            next_step="Write tests",
            latest_actor="test-actor",
        )
        mock_store.add_event.assert_called_once()

    def test_set_next_step_flow_not_found(self, mock_store) -> None:
        """Test setting next step when flow not found."""
        mock_store.get_flow_state.return_value = None

        service = TaskService(store=mock_store)
        with pytest.raises(RuntimeError, match="Flow not found"):
            service.set_next_step(
                branch="nonexistent-branch",
                next_step="Write tests",
                actor="test-actor",
            )