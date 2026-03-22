"""Tests for Flow creation functionality."""

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
            actor="test-actor",
        )

        assert isinstance(result, FlowState)
        assert result.flow_slug == "test-flow"
        assert result.branch == "test-branch"
        assert result.flow_status == "active"

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

    def test_create_flow_no_task_id(self, mock_store) -> None:
        """create_flow no longer accepts task_id; binding via TaskService."""
        service = FlowService(store=mock_store)
        result = service.create_flow(
            slug="test-flow",
            branch="test-branch",
            actor="test-actor",
        )

        assert result.flow_slug == "test-flow"
        # No add_issue_link call — task binding is separate
        mock_store.add_issue_link.assert_not_called()
