"""Tests for flow block with body projection."""

from unittest.mock import MagicMock, patch

from vibe3.services.flow_service import FlowService


def test_block_flow_calls_blocked_state_service() -> None:
    """Test that block_flow calls BlockedStateService.block method."""
    service = FlowService()

    with (
        patch.object(service.store, "get_flow_state") as mock_get,
        patch.object(service.store, "get_issue_links") as mock_get_links,
        patch.object(service.store, "update_flow_state"),
        patch.object(service.store, "add_event"),
        patch("vibe3.services.task_service.TaskService"),
        patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
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


def test_project_blocked_state_updates_issue_body() -> None:
    """Test that _project_blocked_state correctly updates issue body."""
    service = FlowService()

    with patch("vibe3.services.flow_block_mixin.GitHubClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.get_issue_body.return_value = "User content"
        mock_client.update_issue_body.return_value = True

        # Execute
        service._project_blocked_state(
            issue_number=123,
            blocked_by_issue=456,
            reason="API design pending",
        )

        # Verify get_issue_body called
        mock_client.get_issue_body.assert_called_once_with(123)

        # Verify update_issue_body called with merged content
        mock_client.update_issue_body.assert_called_once()
        call_args = mock_client.update_issue_body.call_args
        assert call_args[0][0] == 123  # issue_number
        merged_body = call_args[0][1]

        # Verify managed section contains expected content
        assert "User content" in merged_body
        assert "- **State**: blocked" in merged_body
        assert "#456" in merged_body
        assert "API design pending" in merged_body


def test_project_blocked_state_accumulates_blockers() -> None:
    """Test that _project_blocked_state accumulates multiple blockers."""
    service = FlowService()

    # Mock issue body with existing blocked_by #100
    existing_body = """User content

<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #100

<!-- vibe3-flow-state-end -->"""

    with patch("vibe3.services.flow_block_mixin.GitHubClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.get_issue_body.return_value = existing_body
        mock_client.update_issue_body.return_value = True

        # Execute: add new blocker #200
        service._project_blocked_state(
            issue_number=123,
            blocked_by_issue=200,
            reason="Another dependency",
        )

        # Verify update_issue_body called
        mock_client.update_issue_body.assert_called_once()
        call_args = mock_client.update_issue_body.call_args
        merged_body = call_args[0][1]

        # Verify both #100 and #200 are present (accumulated)
        assert "#100" in merged_body
        assert "#200" in merged_body
        assert "Another dependency" in merged_body


def test_project_blocked_state_idempotent_for_duplicate() -> None:
    """Test that _project_blocked_state is idempotent for duplicate blockers."""
    service = FlowService()

    # Mock issue body with existing blocked_by #100
    existing_body = """User content

<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #100

<!-- vibe3-flow-state-end -->"""

    with patch("vibe3.services.flow_block_mixin.GitHubClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.get_issue_body.return_value = existing_body
        mock_client.update_issue_body.return_value = True

        # Execute: add same blocker #100 again with reason=None (idempotent path)
        service._project_blocked_state(
            issue_number=123,
            blocked_by_issue=100,
            reason=None,  # Keep reason unchanged to trigger no-op
        )

        # Verify update_issue_body NOT called (idempotent, no change)
        mock_client.update_issue_body.assert_not_called()
