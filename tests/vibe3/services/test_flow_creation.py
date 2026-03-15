"""Tests for Flow creation functionality."""
from vibe3.services.flow_service import FlowService
from vibe3.models.flow import FlowState


class TestFlowCreation:
    """Tests for creating flows."""

    def test_create_flow_success(self, mock_store) -> None:
        """Test creating a flow successfully."""
        service = FlowService(store=mock_store)
        result = service.create_flow(
            slug="test-flow",
            branch="test-branch",
            actor="test-actor",
        )

        assert isinstance(result, FlowState)
        assert result.flow_slug == "test-flow"
        assert result.branch == "test-branch"
        assert result.flow_status == "active"

        # Verify store calls
        mock_store.update_flow_state.assert_called_once_with(
            "test-branch",
            flow_slug="test-flow",
            latest_actor="test-actor",
        )
        mock_store.add_event.assert_called_once_with(
            "test-branch",
            "flow_created",
            "test-actor",
            "Flow 'test-flow' created",
        )

    def test_create_flow_with_task(self, mock_store) -> None:
        """Test creating a flow with initial task binding."""
        service = FlowService(store=mock_store)
        result = service.create_flow(
            slug="test-flow",
            branch="test-branch",
            actor="test-actor",
            task_id="TASK-123",
        )

        assert result.flow_slug == "test-flow"
        mock_store.update_flow_state.assert_called()