"""Tests for flow block with body projection."""

from unittest.mock import MagicMock, patch

from vibe3.services.flow.service import FlowService


def test_block_flow_calls_blocked_state_service() -> None:
    """Test that block_flow calls BlockedStateService.block method."""
    service = FlowService()

    with (
        patch.object(service.store, "get_flow_state") as mock_get,
        patch.object(service.store, "get_issue_links") as mock_get_links,
        patch.object(service.store, "update_flow_state"),
        patch.object(service.store, "add_event"),
        patch("vibe3.services.task.service.TaskService"),
        patch(
            "vibe3.services.flow.blocked_state_service.BlockedStateService"
        ) as mock_blocked_service_cls,
    ):

        # Setup mocks
        mock_get.return_value = {
            "branch": "dev/issue-123",
            "task_issue_number": 123,
            "latest_actor": "claude/sonnet-4.6",
        }

        # Mock get_issue_links to return task issue link
        mock_get_links.return_value = [{"issue_number": 123, "issue_role": "task"}]

        mock_blocked_instance = MagicMock()
        mock_blocked_service_cls.return_value = mock_blocked_instance

        # Execute
        service.block_flow(
            branch="dev/issue-123",
            reason="API design pending",
            blocked_by_issue=456,
            actor="claude/sonnet-4.6",
        )

        # Verify BlockedStateService.block called with correct args
        mock_blocked_instance.block.assert_called_once_with(
            branch="dev/issue-123",
            reason="API design pending",
            blocked_by_issue=456,
            actor="claude/sonnet-4.6",
            issue_number=123,
            event_type="flow_blocked",
        )
