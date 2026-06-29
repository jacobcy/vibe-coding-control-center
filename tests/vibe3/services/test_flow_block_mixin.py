"""Tests for flow block with body projection."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.flow.service import FlowService


@pytest.mark.parametrize(
    ("blocked_by_issue", "expected_tasks"),
    [
        (456, [456]),
        (None, []),
    ],
)
def test_block_flow_calls_set_block(
    blocked_by_issue: int | None,
    expected_tasks: list[int],
) -> None:
    """Test that block_flow calls BlockedStateService.set_block method."""
    service = FlowService()

    with (
        patch.object(service.store, "get_flow_state") as mock_get,
        patch.object(service.store, "get_issue_links") as mock_get_links,
        patch.object(service.store, "update_flow_state"),
        patch.object(service.store, "add_event"),
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
            blocked_by_issue=blocked_by_issue,
            actor="claude/sonnet-4.6",
        )

        # Verify BlockedStateService.set_block called with correct args
        mock_blocked_instance.set_block.assert_called_once_with(
            issue_number=123,
            branch="dev/issue-123",
            reason="API design pending",
            tasks=expected_tasks,
            actor="claude/sonnet-4.6",
        )
