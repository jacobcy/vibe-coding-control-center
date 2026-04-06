"""Integration tests for manager abandon flow."""

from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.abandon_flow_service import AbandonFlowService


class TestManagerAbandonIntegration:
    """Tests for manager abandon flow integration."""

    def test_abandon_flow_service_is_used_for_ready_abandon(self):
        """Verify AbandonFlowService coordinates READY abandon correctly."""
        # This test verifies the integration at the service level
        mock_ready_close = MagicMock()
        mock_pr_service = MagicMock()
        mock_flow_service = MagicMock()

        abandon_service = AbandonFlowService(
            ready_close=mock_ready_close,
            pr_service=mock_pr_service,
            flow_service=mock_flow_service,
        )

        # Execute abandon from READY state
        mock_ready_close.close_ready_issue.return_value = "closed"
        mock_pr_service.close_open_pr_for_flow.return_value = None
        mock_flow_service.abort_flow.return_value = None

        result = abandon_service.abandon_flow(
            issue_number=123,
            branch="task/issue-123",
            source_state=IssueState.READY,
            reason="Test abandon",
            actor="agent:manager",
        )

        # Verify all three services were called
        mock_ready_close.close_ready_issue.assert_called_once()
        mock_pr_service.close_open_pr_for_flow.assert_called_once()
        mock_flow_service.abort_flow.assert_called_once()

        # Verify result structure
        assert result["issue"] == "closed"
        assert result["pr"] is None
        assert result["flow"] == "aborted"

    def test_abandon_flow_service_is_used_for_handoff_abandon(self):
        """Verify AbandonFlowService handles HANDOFF abandon with PR close."""
        mock_ready_close = MagicMock()
        mock_pr_service = MagicMock()
        mock_flow_service = MagicMock()

        abandon_service = AbandonFlowService(
            ready_close=mock_ready_close,
            pr_service=mock_pr_service,
            flow_service=mock_flow_service,
        )

        # Execute abandon from HANDOFF state with PR
        mock_ready_close.close_ready_issue.return_value = "closed"
        mock_pr_service.close_open_pr_for_flow.return_value = 456
        mock_flow_service.abort_flow.return_value = None

        result = abandon_service.abandon_flow(
            issue_number=789,
            branch="task/issue-789",
            source_state=IssueState.HANDOFF,
            reason="Test abandon",
            actor="agent:manager",
        )

        # Verify all three services were called
        mock_ready_close.close_ready_issue.assert_called_once()
        mock_pr_service.close_open_pr_for_flow.assert_called_once()
        mock_flow_service.abort_flow.assert_called_once()

        # Verify PR was closed
        assert result["pr"] == 456
