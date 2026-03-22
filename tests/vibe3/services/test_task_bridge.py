"""Tests for task bridge behavior."""

from unittest.mock import MagicMock

from vibe3.models.project_item import LinkError, ProjectItemData, ProjectItemError
from vibe3.models.task_bridge import HydrateError
from vibe3.services.task_service import TaskService


class TestTaskBridgeLinking:
    """Tests for linking local flow to remote project item."""

    def test_link_project_item_requires_existing_flow(self, mock_store) -> None:
        """link-project must attach to an existing flow, not create a shell row."""
        mock_store.get_flow_state.return_value = None
        mock_client = MagicMock()
        mock_client.get_item.return_value = ProjectItemData(
            item_id="PVTI_123",
            node_id="NODE_123",
        )

        service = TaskService(store=mock_store, project_client=mock_client)
        result = service.link_project_item("missing-branch", "PVTI_123")

        assert isinstance(result, LinkError)
        assert result.type == "flow_not_found"
        mock_store.update_bridge_fields.assert_not_called()
        mock_store.add_event.assert_not_called()


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
