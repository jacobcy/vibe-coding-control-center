"""Tests for resuming aborted flows."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestration import IssueState
from vibe3.services.status_query_service import StatusQueryService
from vibe3.services.task_resume_usecase import TaskResumeUsecase


@pytest.fixture
def mock_status_service():
    """Mock StatusQueryService."""
    return MagicMock(spec=StatusQueryService)


@pytest.fixture
def mock_label_service():
    """Mock LabelService."""
    return MagicMock()


@pytest.fixture
def mock_flow_service():
    """Mock FlowService."""
    return MagicMock()


@pytest.fixture
def resume_usecase(mock_status_service, mock_label_service, mock_flow_service):
    """Create TaskResumeUsecase with mocked dependencies."""
    return TaskResumeUsecase(
        status_service=mock_status_service,
        label_service=mock_label_service,
        flow_service=mock_flow_service,
    )


class TestAbortedFlowRecovery:
    """Tests for recovering aborted flows."""

    def test_resume_can_reactivate_aborted_flow(
        self, resume_usecase, mock_status_service, mock_flow_service
    ):
        """Aborted flow can be reactivated via resume."""
        # Mock an aborted flow candidate (issue reopened after abandon)
        aborted_flow = FlowStatusResponse(
            branch="task/issue-123",
            flow_slug="issue-123",
            flow_status="aborted",
            latest_actor="agent:manager",
        )

        candidates = [
            {
                "number": 123,
                "title": "Test issue",
                "state": IssueState.READY,
                "flow": aborted_flow,
                "resume_kind": "aborted",
            }
        ]

        mock_status_service.fetch_resume_candidates.return_value = candidates

        # Resume should reactivate the flow
        result = resume_usecase.resume_issues(issue_numbers=[123])

        assert len(result["resumed"]) == 1
        assert result["resumed"][0]["number"] == 123
        assert result["resumed"][0]["resume_kind"] == "aborted"

        # Verify flow was reactivated
        mock_flow_service.reactivate_flow.assert_called_once_with("task/issue-123")

    def test_resume_aborted_flow_preserves_artifacts(
        self, resume_usecase, mock_status_service, mock_flow_service
    ):
        """Resuming aborted flow preserves historical refs."""
        # Mock an aborted flow with historical refs
        aborted_flow = FlowStatusResponse(
            branch="task/issue-456",
            flow_slug="issue-456",
            flow_status="aborted",
            spec_ref="docs/specs/old-spec.md",  # Should be preserved
            plan_ref="docs/plans/old-plan.md",  # Historical ref
        )

        candidates = [
            {
                "number": 456,
                "title": "Test issue with history",
                "state": IssueState.HANDOFF,
                "flow": aborted_flow,
                "resume_kind": "aborted",
            }
        ]

        mock_status_service.fetch_resume_candidates.return_value = candidates

        # Resume the aborted flow
        result = resume_usecase.resume_issues(issue_numbers=[456])

        assert len(result["resumed"]) == 1

        # Verify reactivate was called (which preserves refs via events)
        mock_flow_service.reactivate_flow.assert_called_once()
