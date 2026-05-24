"""Tests for clear operations (flow reasons and blocked projection)."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services.task_resume_operations import TaskResumeOperations


def test_clear_flow_reasons_clears_both_reasons(
    make_operations: TaskResumeOperations,
) -> None:
    """_clear_flow_reasons should use BlockedStateService.unblock."""
    operations = make_operations

    with (
        patch.object(
            operations.flow_service.store, "get_task_issue_number"
        ) as mock_get_issue,
        patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_blocked_service_cls,
    ):
        mock_get_issue.return_value = 303
        mock_blocked_instance = MagicMock()
        mock_blocked_service_cls.return_value = mock_blocked_instance

        operations._clear_flow_reasons("task/issue-303", "blocked")

        mock_blocked_instance.unblock.assert_called_once_with(
            branch="task/issue-303",
            target_state=IssueState.CLAIMED,
            actor="human:resume",
            issue_number=303,
        )


def test_clear_flow_reasons_uses_blocked_state_service(
    make_operations: TaskResumeOperations,
) -> None:
    """Test that _clear_flow_reasons uses BlockedStateService.unblock."""
    operations = make_operations

    with (
        patch.object(
            operations.flow_service.store, "get_task_issue_number"
        ) as mock_get_issue,
        patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_blocked_service_cls,
    ):
        mock_get_issue.return_value = 123
        mock_blocked_instance = MagicMock()
        mock_blocked_service_cls.return_value = mock_blocked_instance

        # Execute
        operations._clear_flow_reasons("task/issue-123", "blocked")

        # Verify BlockedStateService.unblock called with correct args
        mock_blocked_instance.unblock.assert_called_once_with(
            branch="task/issue-123",
            target_state=IssueState.CLAIMED,
            actor="human:resume",
            issue_number=123,
        )


def test_clear_blocked_projection_updates_issue_body(
    make_operations: TaskResumeOperations,
) -> None:
    """Test that _clear_blocked_projection correctly clears managed section."""
    operations = make_operations

    # Mock issue body with blocked state
    blocked_body = """User content here.

<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456
- **Blocked reason**: API design pending

<!-- vibe3-flow-state-end -->"""

    with patch.object(operations.github_client, "get_issue_body") as mock_get:
        mock_get.return_value = blocked_body

        with patch.object(operations.github_client, "update_issue_body") as mock_update:
            mock_update.return_value = True

            # Execute
            operations._clear_blocked_projection(123)

            # Verify get_issue_body called
            mock_get.assert_called_once_with(123)

            # Verify update_issue_body called
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == 123  # issue_number
            merged_body = call_args[0][1]

            # Verify managed section is cleared (empty projection)
            assert "User content here" in merged_body
            assert "**Vibe3 Flow State**" not in merged_body
            assert "- **State**: blocked" not in merged_body


def test_clear_blocked_projection_handles_none_body(
    make_operations: TaskResumeOperations,
) -> None:
    """Test that _clear_blocked_projection handles missing issue body."""
    operations = make_operations

    with patch.object(operations.github_client, "get_issue_body") as mock_get:
        mock_get.return_value = None

        with patch.object(operations.github_client, "update_issue_body") as mock_update:
            # Execute
            operations._clear_blocked_projection(123)

            # Verify update_issue_body not called when body is None
            mock_update.assert_not_called()
