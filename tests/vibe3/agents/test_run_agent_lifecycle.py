"""Tests for RunUsecase.build_lifecycle_callbacks."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.agents.run_agent import RunUsecase
from vibe3.domain.events import IssueFailed, IssueStateChanged
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_service import FlowService


def test_build_lifecycle_callbacks_success():
    """测试 on_success 闭包在有 handoff_file 时发布 IssueStateChanged 事件."""
    from vibe3.agents.models import CodeagentResult

    flow_service = MagicMock(spec=FlowService)
    usecase = RunUsecase(flow_service=flow_service)

    # Create a result with handoff_file
    result = CodeagentResult(
        success=True,
        exit_code=0,
        stdout="",
        stderr="",
        handoff_file=Path("/tmp/handoff.md"),  # Has handoff file
        session_id=None,
        pid=None,
        tmux_session=None,
        log_path=None,
    )

    # MUST patch before calling build_lifecycle_callbacks
    # because of local import and closure
    with patch("vibe3.domain.publisher.publish") as mock_publish:
        on_success, on_failure = usecase.build_lifecycle_callbacks(
            issue_number=123, branch="test-branch", flow_service=flow_service
        )

        # Call on_success with result
        on_success(result)

        # Verify only one event published: IssueStateChanged (has handoff_file)
        assert mock_publish.call_count == 1

        # Check event: IssueStateChanged
        event = mock_publish.call_args[0][0]
        assert isinstance(event, IssueStateChanged)
        assert event.issue_number == 123
        assert event.to_state == IssueState.HANDOFF.value


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
