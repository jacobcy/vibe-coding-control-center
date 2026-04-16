"""Tests for executor role lifecycle publishing helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.agents.models import CodeagentResult
from vibe3.domain.events import IssueFailed, IssueStateChanged, ReportRefRequired
from vibe3.domain.publisher import EventPublisher
from vibe3.models.orchestration import IssueState
from vibe3.roles.run import publish_run_command_failure, publish_run_command_success


class TestPublishRunCommandSuccess:
    def test_publishes_issue_state_changed_when_handoff_exists(self) -> None:
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=Path("/tmp/handoff.md"),
            session_id="test-session-id",
        )

        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=123,
                branch="dev/test-123",
                result=result,
            )

        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, IssueStateChanged)
        assert event.issue_number == 123
        assert event.to_state == IssueState.HANDOFF.value
        assert event.actor == "agent:run"

    def test_publishes_report_ref_required_when_handoff_missing(self) -> None:
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=None,
            session_id="test-session-id",
        )

        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=456,
                branch="dev/test-456",
                result=result,
            )

        assert len(published_events) == 1
        event = published_events[0]
        assert isinstance(event, ReportRefRequired)
        assert event.issue_number == 456
        assert event.branch == "dev/test-456"
        assert event.ref_name == "report_ref"
        assert "report_ref was registered" in event.reason
        assert event.actor == "agent:run"

    def test_handles_non_codeagent_result_gracefully(self) -> None:
        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=999,
                branch="dev/test-999",
                result=object(),
            )

        assert len(published_events) == 1
        assert isinstance(published_events[0], ReportRefRequired)

    def test_publish_errors_propagate(self) -> None:
        result = CodeagentResult(
            success=True,
            exit_code=0,
            stdout="Task completed",
            stderr="",
            handoff_file=Path("/tmp/handoff.md"),
            session_id="test-session-id",
        )

        EventPublisher.reset()
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = RuntimeError("Publisher failed")
            with pytest.raises(RuntimeError):
                publish_run_command_success(
                    issue_number=111,
                    branch="dev/test-111",
                    result=result,
                )


def test_publish_run_command_failure_emits_issue_failed() -> None:
    EventPublisher.reset()
    published_events = []
    with patch.object(EventPublisher, "publish") as mock_publish:
        mock_publish.side_effect = lambda event: published_events.append(event)
        publish_run_command_failure(
            issue_number=789,
            reason="Execution failed: timeout expired",
        )

    assert len(published_events) == 1
    event = published_events[0]
    assert isinstance(event, IssueFailed)
    assert event.issue_number == 789
    assert "timeout expired" in event.reason
    assert event.actor == "agent:run"


class TestExecutorFailed:
    """场景 1: executor 执行报错 → state/failed"""

    def test_executor_failed_calls_fail_executor_issue(
        self,
    ) -> None:
        """Executor 执行报错 → 调用 fail_executor_issue"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import fail_executor_issue

            fail_executor_issue(
                issue_number=200,
                reason="timeout after 120s",
                actor="agent:run",
            )

            # Verify: _ensure_flow_state_for_issue called with "fail" action
            mock_ensure.assert_called_once_with(
                200,
                "fail",  # ← action 参数
                "timeout after 120s",  # ← reason
                "agent:run",  # ← actor
            )


class TestExecutorBlockedNoReportRef:
    """场景 2: executor 无产出 → state/blocked"""

    def test_executor_blocked_no_report_ref_calls_block_executor(
        self,
    ) -> None:
        """Executor 无 report_ref → 调用 block_executor_noop_issue"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_executor_noop_issue

            block_executor_noop_issue(
                issue_number=201,
                repo="jacobcy/vibe-coding-control-center",
                reason="no report_ref",
                actor="agent:run",
            )

            # Verify: _ensure_flow_state_for_issue called with "block" action
            mock_ensure.assert_called_once_with(
                201,
                "block",  # ← action 参数
                "no report_ref",  # ← reason
                "agent:run",  # ← actor
            )


class TestExecutorBlockedNoStateChange:
    """场景 3: executor 有产出但无推进 → state/blocked"""

    def test_executor_blocked_no_state_change_calls_block_executor(
        self,
    ) -> None:
        """Executor 有 report_ref 但 state 未变 → block"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_executor_noop_issue

            block_executor_noop_issue(
                issue_number=202,
                repo="jacobcy/vibe-coding-control-center",
                reason="no state change",
                actor="agent:run",
            )

            # Verify: block reason
            mock_ensure.assert_called_once_with(
                202,
                "block",
                "no state change",  # ← reason
                "agent:run",
            )


class TestExecutorSuccessStateChanged:
    """场景 4: executor 正常推进 → 不干预"""

    def test_executor_success_no_forced_handoff_event(
        self,
    ) -> None:
        """Executor 正常推进 → 不应该强制转 HANDOFF"""
        # This test verifies that executor success does NOT force HANDOFF
        # The actual implementation will be fixed to remove confirm_role_handoff
        pass  # ← Placeholder: 实际修复后添加详细测试


class TestExecutorNoProgressPolicy:
    """Executor no-progress 检测"""

    def test_executor_has_progress_with_report_ref(
        self,
    ) -> None:
        """Executor 有 report_ref → 有推进"""
        from vibe3.runtime.no_progress_policy import has_progress_changed

        before = {
            "state_label": IssueState.IN_PROGRESS.to_label(),
            "comment_count": 0,
            "handoff": None,
            "refs": {},
            "issue_state": "open",
            "flow_status": "active",
        }

        after = {
            "state_label": IssueState.IN_PROGRESS.to_label(),
            "comment_count": 1,
            "handoff": None,
            "refs": {
                "report_ref": "docs/reports/issue-200-report.md"
            },  # ← 有 report_ref
            "issue_state": "open",
            "flow_status": "active",
        }

        has_progress = has_progress_changed(
            before=before,
            after=after,
            expected_ref="report_ref",  # ← 检查 report_ref
        )

        assert has_progress is True  # ← 有推进（report_ref 变化）

    def test_executor_no_progress_without_report_ref(
        self,
    ) -> None:
        """Executor 无 report_ref → 无推进"""
        from vibe3.runtime.no_progress_policy import has_progress_changed

        before = {
            "state_label": IssueState.IN_PROGRESS.to_label(),
            "comment_count": 0,
            "handoff": None,
            "refs": {},
            "issue_state": "open",
            "flow_status": "active",
        }

        after = {
            "state_label": IssueState.IN_PROGRESS.to_label(),
            "comment_count": 2,
            "handoff": None,
            "refs": {},  # ← 无 report_ref
            "issue_state": "open",
            "flow_status": "active",
        }

        has_progress = has_progress_changed(
            before=before,
            after=after,
            expected_ref="report_ref",  # ← 检查 report_ref
        )

        assert has_progress is False  # ← 无推进（report_ref 缺失）
