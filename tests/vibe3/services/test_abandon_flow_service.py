"""Tests for AbandonFlowService."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.services.abandon_flow_service import AbandonFlowService


class TestAbandonFlowService:
    """Tests for unified abandonment flow."""

    @pytest.fixture
    def mock_ready_close(self):
        """Mock ReadyCloseService."""
        return MagicMock()

    @pytest.fixture
    def mock_pr_service(self):
        """Mock PRService."""
        return MagicMock()

    @pytest.fixture
    def mock_flow_service(self):
        """Mock FlowService."""
        return MagicMock()

    @pytest.fixture
    def abandon_service(self, mock_ready_close, mock_pr_service, mock_flow_service):
        """Create AbandonFlowService with mocked dependencies."""
        return AbandonFlowService(
            ready_close=mock_ready_close,
            pr_service=mock_pr_service,
            flow_service=mock_flow_service,
        )

    def test_manager_ready_abandon_closes_issue_and_aborts_flow(
        self, abandon_service, mock_ready_close, mock_pr_service, mock_flow_service
    ):
        """Abandon from ready state closes issue and aborts flow."""
        mock_ready_close.close_ready_issue.return_value = "closed"
        mock_pr_service.close_open_pr_for_flow.return_value = None  # No PR

        result = abandon_service.abandon_flow(
            issue_number=123,
            branch="task/issue-123",
            source_state=IssueState.READY,
            reason="Task no longer needed",
            actor="agent:manager",
        )

        assert result["issue"] == "closed"
        assert result["pr"] is None
        assert result["flow"] == "aborted"

        mock_ready_close.close_ready_issue.assert_called_once_with(
            123, closing_comment="[manager] 任务放弃。\n\n原因:Task no longer needed"
        )
        mock_pr_service.close_open_pr_for_flow.assert_called_once_with(
            branch="task/issue-123",
            comment="[manager] PR 放弃。\n\n原因:Task no longer needed",
        )
        mock_flow_service.abort_flow.assert_called_once_with(
            branch="task/issue-123",
            reason="Task no longer needed",
            actor="agent:manager",
        )

    def test_manager_handoff_abandon_closes_issue_pr_and_aborts_flow(
        self, abandon_service, mock_ready_close, mock_pr_service, mock_flow_service
    ):
        """Abandon from handoff state closes issue, PR, and aborts flow."""
        mock_ready_close.close_ready_issue.return_value = "closed"
        mock_pr_service.close_open_pr_for_flow.return_value = 456  # PR closed

        result = abandon_service.abandon_flow(
            issue_number=789,
            branch="task/issue-789",
            source_state=IssueState.HANDOFF,
            reason="Invalid task",
            actor="agent:manager",
        )

        assert result["issue"] == "closed"
        assert result["pr"] == 456
        assert result["flow"] == "aborted"

    def test_abandon_continues_on_partial_failures(
        self, abandon_service, mock_ready_close, mock_pr_service, mock_flow_service
    ):
        """Abandon continues even if some steps fail."""
        # Issue close fails
        mock_ready_close.close_ready_issue.side_effect = Exception("Issue API error")
        # PR close succeeds
        mock_pr_service.close_open_pr_for_flow.return_value = 456
        # Flow abort succeeds
        mock_flow_service.abort_flow.return_value = None

        result = abandon_service.abandon_flow(
            issue_number=123,
            branch="task/issue-123",
            source_state=IssueState.READY,
            reason="Test",
        )

        # Should complete all steps despite partial failures
        assert result["issue"] == "failed"
        assert result["pr"] == 456
        assert result["flow"] == "aborted"

        # Verify all services were called
        mock_ready_close.close_ready_issue.assert_called_once()
        mock_pr_service.close_open_pr_for_flow.assert_called_once()
        mock_flow_service.abort_flow.assert_called_once()
