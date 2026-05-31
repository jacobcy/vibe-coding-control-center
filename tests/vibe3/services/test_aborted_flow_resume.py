"""Tests for resuming aborted flows.

After simplification: aborted flows go through the same reset_issue_to_ready
path as all other resume kinds. No special reactivation logic.
"""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestration import IssueState
from vibe3.services.status_query_service import StatusQueryService
from vibe3.services.task_resume_usecase import TaskResumeUsecase


@pytest.fixture
def mock_status_service():
    return MagicMock(spec=StatusQueryService)


@pytest.fixture
def mock_label_service():
    return MagicMock()


@pytest.fixture
def mock_flow_service():
    return MagicMock()


@pytest.fixture
def resume_usecase(mock_status_service, mock_label_service, mock_flow_service):
    return TaskResumeUsecase(
        status_service=mock_status_service,
        label_service=mock_label_service,
        flow_service=mock_flow_service,
    )


class TestAbortedFlowRecovery:

    def test_resume_aborted_flow_uses_unified_path(
        self, resume_usecase, mock_status_service
    ):
        """Aborted flow goes through reset_issue_to_ready like all other kinds."""
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
        resume_usecase.candidates.verify_issue_state_for_resume = MagicMock(
            return_value=True
        )

        with patch.object(
            resume_usecase.operations, "reset_issue_to_ready"
        ) as mock_reset:
            result = resume_usecase.resume_issues(issue_numbers=[123])

            assert len(result["resumed"]) == 1
            assert result["resumed"][0]["resume_kind"] == "aborted"

            mock_reset.assert_called_once()
            call_kwargs = mock_reset.call_args.kwargs
            assert call_kwargs["resume_kind"] == "aborted"
            assert call_kwargs["issue_number"] == 123
