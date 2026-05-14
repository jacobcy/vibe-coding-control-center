"""Test refactored block_manager_noop_issue() that reuses block_flow()."""

from unittest.mock import Mock, patch

from vibe3.services.issue_failure_service import block_manager_noop_issue


def test_block_manager_noop_issue_reuses_block_flow():
    """block_manager_noop_issue() should call block_flow() internally."""
    with patch(
        "vibe3.services.issue_failure_service._get_issue_flow_service"
    ) as mock_get_service:
        mock_service = Mock()
        mock_store = Mock()
        mock_service.store = mock_store
        mock_get_service.return_value = mock_service

        # Mock flow data
        mock_store.get_flows_by_issue.return_value = [
            {"branch": "task/issue-123", "task_issue_number": 123}
        ]

        with patch("vibe3.services.flow_service.FlowService") as mock_flow_service:
            mock_flow_instance = mock_flow_service.return_value

            block_manager_noop_issue(
                issue_number=123, repo=None, reason="Test reason", actor="test:actor"
            )

            # Verify block_flow was called with correct parameters
            mock_flow_instance.block_flow.assert_called_once_with(
                "task/issue-123", reason="Test reason", actor="test:actor"
            )


def test_block_manager_noop_issue_adds_blocked_event():
    """block_manager_noop_issue() should still add 'blocked' event."""
    with patch(
        "vibe3.services.issue_failure_service._get_issue_flow_service"
    ) as mock_get_service:
        mock_service = Mock()
        mock_store = Mock()
        mock_service.store = mock_store
        mock_get_service.return_value = mock_service

        mock_store.get_flows_by_issue.return_value = [{"branch": "task/issue-123"}]

        with patch("vibe3.services.flow_service.FlowService"):
            block_manager_noop_issue(
                issue_number=123, repo=None, reason="Test reason", actor="test:actor"
            )

            # Verify blocked event was added (separate from flow_blocked)
            mock_store.add_event.assert_called_once_with(
                "task/issue-123",
                "blocked",
                "test:actor",
                detail="Test reason",
                refs={"issue": "123"},
            )


def test_block_manager_noop_issue_no_flow():
    """block_manager_noop_issue() should return early if no flow exists."""
    with patch(
        "vibe3.services.issue_failure_service._get_issue_flow_service"
    ) as mock_get_service:
        mock_service = Mock()
        mock_store = Mock()
        mock_service.store = mock_store
        mock_get_service.return_value = mock_service

        # No flow found
        mock_store.get_flows_by_issue.return_value = []

        with patch("vibe3.services.flow_service.FlowService") as mock_flow_service:
            block_manager_noop_issue(
                issue_number=123, repo=None, reason="Test reason", actor="test:actor"
            )

            # Should NOT call block_flow
            mock_flow_service.return_value.block_flow.assert_not_called()
