"""Tests for RunUsecase.build_lifecycle_callbacks."""

from unittest.mock import MagicMock, patch

from vibe3.agents.run_agent import RunUsecase
from vibe3.domain.events import IssueFailed, IssueStateChanged, ReportRefRequired
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_service import FlowService


def test_build_lifecycle_callbacks_success():
    """测试 on_success 闭包发布事件流程."""
    flow_service = MagicMock(spec=FlowService)
    usecase = RunUsecase(flow_service=flow_service)

    # MUST patch before calling build_lifecycle_callbacks
    # because of local import and closure
    with patch("vibe3.domain.publisher.publish") as mock_publish:
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number=123, branch="test-branch", flow_service=flow_service
        )

        # Call on_success
        on_success(object())

        # Verify two events published: ReportRefRequired and IssueStateChanged
        assert mock_publish.call_count == 2

        # Check first event: ReportRefRequired
        event1 = mock_publish.call_args_list[0][0][0]
        assert isinstance(event1, ReportRefRequired)
        assert event1.issue_number == 123
        assert event1.ref_name == "report_ref"

        # Check second event: IssueStateChanged
        event2 = mock_publish.call_args_list[1][0][0]
        assert isinstance(event2, IssueStateChanged)
        assert event2.issue_number == 123
        assert event2.to_state == IssueState.HANDOFF.value


def test_build_lifecycle_callbacks_failure():
    """测试 on_failure 闭包发布 IssueFailed 事件."""
    flow_service = MagicMock(spec=FlowService)
    usecase = RunUsecase(flow_service=flow_service)

    with patch("vibe3.domain.publisher.publish") as mock_publish:
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number=123, branch="test-branch", flow_service=flow_service
        )

        error = Exception("Test error")
        on_failure(error)

        # Verify IssueFailed event published
        mock_publish.assert_called_once()
        event = mock_publish.call_args[0][0]
        assert isinstance(event, IssueFailed)
        assert event.issue_number == 123
        assert event.reason == "Test error"


def test_build_lifecycle_callbacks_failure_with_complex_error():
    """测试 on_failure 处理复杂错误信息并发布事件."""
    flow_service = MagicMock(spec=FlowService)
    usecase = RunUsecase(flow_service=flow_service)

    with patch("vibe3.domain.publisher.publish") as mock_publish:
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number=456, branch="test-branch", flow_service=flow_service
        )

        error = Exception("Multi-line\nerror\nmessage")
        on_failure(error)

        # Verify IssueFailed event published
        mock_publish.assert_called_once()
        event = mock_publish.call_args[0][0]
        assert isinstance(event, IssueFailed)
        assert event.issue_number == 456
        assert event.reason == "Multi-line\nerror\nmessage"
