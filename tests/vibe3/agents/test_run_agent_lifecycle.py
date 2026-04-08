"""Tests for RunUsecase.build_lifecycle_callbacks."""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.agents.run_agent import RunUsecase
from vibe3.services.flow_service import FlowService


def test_build_lifecycle_callbacks_success():
    """测试 on_success 闭包正常流程."""
    flow_service = MagicMock(spec=FlowService)
    usecase = RunUsecase(flow_service=flow_service)

    on_success, on_failure = usecase.build_lifecycle_callbacks(
        issue_number=123, branch="test-branch", flow_service=flow_service
    )

    # Mock dependencies
    with (
        patch("vibe3.agents.run_agent.require_authoritative_ref") as mock_require,
        patch("vibe3.agents.run_agent.LabelService") as mock_label_svc,
    ):
        mock_require.return_value = True
        mock_confirm = MagicMock()
        mock_label_svc.return_value.confirm_issue_state = mock_confirm

        # Call on_success
        on_success(object())

        # Verify
        mock_require.assert_called_once()
        mock_confirm.assert_called_once_with(123, "handoff", actor="agent:run")


def test_build_lifecycle_callbacks_require_ref_failed():
    """测试 require_authoritative_ref 失败时抛出异常."""
    flow_service = MagicMock(spec=FlowService)
    usecase = RunUsecase(flow_service=flow_service)

    on_success, on_failure = usecase.build_lifecycle_callbacks(
        issue_number=123, branch="test-branch", flow_service=flow_service
    )

    # Mock require_authoritative_ref to return False
    with patch("vibe3.agents.run_agent.require_authoritative_ref") as mock_require:
        mock_require.return_value = False

        # Call on_success and expect exception
        with pytest.raises(Exception, match="Executor completed without report_ref"):
            on_success(object())


def test_build_lifecycle_callbacks_failure():
    """测试 on_failure 闭包标记失败状态."""
    flow_service = MagicMock(spec=FlowService)
    usecase = RunUsecase(flow_service=flow_service)

    on_success, on_failure = usecase.build_lifecycle_callbacks(
        issue_number=123, branch="test-branch", flow_service=flow_service
    )

    # Mock fail_executor_issue
    with patch("vibe3.agents.run_agent.fail_executor_issue") as mock_fail:
        error = Exception("Test error")
        on_failure(error)

        # Verify
        mock_fail.assert_called_once_with(
            issue_number=123,
            reason="Test error",
            actor="agent:run",
        )


def test_build_lifecycle_callbacks_failure_with_complex_error():
    """测试 on_failure 处理复杂错误信息."""
    flow_service = MagicMock(spec=FlowService)
    usecase = RunUsecase(flow_service=flow_service)

    on_success, on_failure = usecase.build_lifecycle_callbacks(
        issue_number=456, branch="test-branch", flow_service=flow_service
    )

    # Mock fail_executor_issue
    with patch("vibe3.agents.run_agent.fail_executor_issue") as mock_fail:
        error = Exception("Multi-line\nerror\nmessage")
        on_failure(error)

        # Verify
        mock_fail.assert_called_once_with(
            issue_number=456,
            reason="Multi-line\nerror\nmessage",
            actor="agent:run",
        )
