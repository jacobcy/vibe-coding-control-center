"""Tests for task bridge behavior."""

from unittest.mock import MagicMock

from vibe3.models.project_item import ProjectItemError
from vibe3.models.task_bridge import HydrateError
from vibe3.services.task_service import TaskService


class TestTaskBridgeHydration:
    """Tests for hydrating task bridge from remote project data."""

    def test_hydrate_not_found_returns_binding_invalid(self, mock_store) -> None:
        """A missing remote item should be treated as broken binding, not offline."""
        mock_store.get_flow_state.return_value = {
            "branch": "test-branch",
            "flow_slug": "test-flow",
            "project_item_id": "PVTI_123",
            "project_node_id": "NODE_123",
            "task_issue_number": 220,
        }
        mock_client = MagicMock()
        mock_client.get_item.return_value = ProjectItemError(
            type="not_found",
            message="item missing",
        )

        service = TaskService(store=mock_store, project_client=mock_client)
        result = service.hydrate("test-branch")

        assert isinstance(result, HydrateError)
        assert result.type == "binding_invalid"

    def test_hydrate_network_error_still_uses_offline_mode(self, mock_store) -> None:
        """Network failures should still degrade to offline mode."""
        mock_store.get_flow_state.return_value = {
            "branch": "test-branch",
            "flow_slug": "test-flow",
            "project_item_id": "PVTI_123",
            "project_node_id": "NODE_123",
            "task_issue_number": 220,
        }
        mock_client = MagicMock()
        mock_client.get_item.return_value = ProjectItemError(
            type="network_error",
            message="timeout",
        )

        service = TaskService(store=mock_store, project_client=mock_client)
        result = service.hydrate("test-branch")

        assert not isinstance(result, HydrateError)
        assert result.offline_mode is True
