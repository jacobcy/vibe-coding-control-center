"""Tests for RunUsecase.build_lifecycle_callbacks event publishing.

Regression tests for IssueStateChanged, ReportRefRequired, IssueFailed branches.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.models import CodeagentResult
from vibe3.agents.run_agent import RunUsecase
from vibe3.domain.events import IssueFailed, IssueStateChanged, ReportRefRequired
from vibe3.domain.publisher import EventPublisher
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_service import FlowService


class TestBuildLifecycleCallbacks:
    """Test event publishing callbacks for run execution."""

    def test_on_success_publishes_issue_state_changed_when_handoff_exists(
        self,
    ) -> None:
        """When handoff_file exists, on_success publishes IssueStateChanged(HANDOFF)."""
        issue_number = 123
        branch = "dev/test-123"
        mock_flow_service = MagicMock(spec=FlowService)

        usecase = RunUsecase()
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number, branch, mock_flow_service
        )

        # Simulate result with handoff_file
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=Path("/tmp/handoff.md"),
            session_id="test-session-id",
        )

        # Reset singleton and mock publish method
        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)

            on_success(result)

        # Verify IssueStateChanged event was published
        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, IssueStateChanged)
        assert event.issue_number == issue_number
        assert event.to_state == IssueState.HANDOFF.value
        assert event.actor == "agent:run"

    def test_on_success_publishes_report_ref_required_when_handoff_missing(
        self,
    ) -> None:
        """When handoff_file is missing, on_success should publish ReportRefRequired."""
        issue_number = 456
        branch = "dev/test-456"
        mock_flow_service = MagicMock(spec=FlowService)

        usecase = RunUsecase()
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number, branch, mock_flow_service
        )

        # Simulate result WITHOUT handoff_file
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=None,  # Missing handoff
            session_id="test-session-id",
        )

        # Reset singleton and mock publish method
        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)

            on_success(result)

        # Verify ReportRefRequired event was published
        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, ReportRefRequired)
        assert event.issue_number == issue_number
        assert event.branch == branch
        assert event.ref_name == "report_ref"
        assert "report_ref was registered" in event.reason
        assert event.actor == "agent:run"

    def test_on_failure_publishes_issue_failed_event(self) -> None:
        """on_failure should publish IssueFailed event with error reason."""
        issue_number = 789
        branch = "dev/test-789"
        mock_flow_service = MagicMock(spec=FlowService)

        usecase = RunUsecase()
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number, branch, mock_flow_service
        )

        # Simulate execution error
        error = Exception("Execution failed: timeout expired")

        # Reset singleton and mock publish method
        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)

            on_failure(error)

        # Verify IssueFailed event was published
        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, IssueFailed)
        assert event.issue_number == issue_number
        assert "timeout expired" in event.reason
        assert event.actor == "agent:run"

    def test_callbacks_handle_non_codeagent_result_gracefully(self) -> None:
        """Callbacks should handle non-CodeagentResult objects."""
        issue_number = 999
        branch = "dev/test-999"
        mock_flow_service = MagicMock(spec=FlowService)

        usecase = RunUsecase()
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number, branch, mock_flow_service
        )

        # Simulate result as plain object (not CodeagentResult)
        result = object()

        # Reset singleton and mock publish method
        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)

            on_success(result)

        # Should publish ReportRefRequired (no handoff_file attribute)
        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, ReportRefRequired)
        assert event.issue_number == issue_number

    def test_callback_errors_propagate_to_caller(self) -> None:
        """Callback errors should propagate to the caller for handling."""
        issue_number = 111
        branch = "dev/test-111"
        mock_flow_service = MagicMock(spec=FlowService)

        usecase = RunUsecase()
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number, branch, mock_flow_service
        )

        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=Path("/tmp/handoff.md"),
            session_id="test-session-id",
        )

        # Reset singleton and mock publish to raise error
        EventPublisher.reset()
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = RuntimeError("Publisher failed")

            # Callback should raise, and the caller should handle it
            with pytest.raises(RuntimeError):
                on_success(result)

    def test_callbacks_dont_use_flow_service_parameter(self) -> None:
        """Callbacks create their own FlowService, deprecated parameter is ignored."""
        issue_number = 222
        branch = "dev/test-222"

        # Create a FlowService with specific behavior
        mock_flow_service = MagicMock(spec=FlowService)
        mock_flow_service.get_flow_status.return_value = None

        usecase = RunUsecase(flow_service=mock_flow_service)
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number, branch, mock_flow_service
        )

        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            handoff_file=None,
            session_id="test-session-id",
        )

        with patch("vibe3.domain.publisher.publish"):
            on_success(result)

        # FlowService parameter is deprecated and should not be used by callbacks
        # Callbacks create their own events directly
        mock_flow_service.get_flow_status.assert_not_called()
