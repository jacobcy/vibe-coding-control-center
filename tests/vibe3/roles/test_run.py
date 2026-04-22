"""Tests for executor role lifecycle publishing helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.agents.models import CodeagentResult
from vibe3.domain.events import IssueFailed
from vibe3.domain.publisher import EventPublisher
from vibe3.roles.run import publish_run_command_failure, publish_run_command_success


class TestPublishRunCommandSuccess:
    """publish_run_command_success records success, does NOT auto-transition state.

    State transitions are the agent's responsibility via run_task instructions.
    Code layer MUST NOT auto-publish HANDOFF (noop-gate-boundary-standard).
    """

    def test_logs_success_without_publishing_events(self) -> None:
        """Success recording should not publish any domain events."""
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
                _branch="dev/test-123",
                _result=result,
            )

        assert len(published_events) == 0

    def test_logs_success_without_handoff_file(self) -> None:
        """Success without handoff file should also not publish events."""
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
                _branch="dev/test-456",
                _result=result,
            )

        assert len(published_events) == 0

    def test_handles_non_codeagent_result_gracefully(self) -> None:
        """Non-CodeagentResult should also not publish events."""
        EventPublisher.reset()
        published_events = []
        with patch.object(EventPublisher, "publish") as mock_publish:
            mock_publish.side_effect = lambda event: published_events.append(event)
            publish_run_command_success(
                issue_number=999,
                _branch="dev/test-999",
                _result=object(),
            )

        assert len(published_events) == 0


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


def test_execute_manual_run_no_async_publishes_issue_failed_on_exception() -> None:
    from types import SimpleNamespace

    from vibe3.roles.run import execute_manual_run

    with (
        patch("vibe3.roles.run.CodeagentExecutionService") as mock_service_cls,
        patch(
            "vibe3.roles.run.make_run_context_builder", return_value=lambda: "prompt"
        ),
        patch("vibe3.roles.run.publish_run_command_failure") as mock_publish_failure,
    ):
        mock_service_cls.return_value.execute_sync.side_effect = RuntimeError(
            "backend returned empty result"
        )

        with pytest.raises(RuntimeError, match="backend returned empty result"):
            execute_manual_run(
                config=object(),
                branch="task/issue-349",
                issue_number=349,
                instructions=None,
                plan_file="docs/plans/issue-349.md",
                skill=None,
                summary=SimpleNamespace(mode="plan"),
                dry_run=False,
                no_async=True,
                agent=None,
                backend=None,
                model=None,
            )

        mock_publish_failure.assert_called_once_with(
            issue_number=349,
            reason="backend returned empty result",
        )


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
    """场景 2: executor 无行动 → state/blocked"""

    def test_executor_blocked_no_report_ref_calls_block_executor(
        self,
    ) -> None:
        """Executor 无行动 → 调用 block_executor_noop_issue"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_executor_noop_issue

            block_executor_noop_issue(
                issue_number=201,
                repo="jacobcy/vibe-coding-control-center",
                reason="state unchanged",
                actor="agent:run",
            )

            # Verify: _ensure_flow_state_for_issue called with "block" action
            mock_ensure.assert_called_once_with(
                201,
                "block",  # ← action 参数
                "state unchanged",  # ← reason
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


class TestExecutorNoOpGate:
    """Executor no-op gate: state 未变 → blocked"""

    def test_executor_blocked_when_state_unchanged(
        self,
    ) -> None:
        """Executor state/in-progress 未变 → blocked"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/in-progress"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=200,
                branch="task/issue-200",
                actor="agent:run",
                role="executor",
                before_state_label="state/in-progress",
            )

        mock_block.assert_called_once()

    def test_executor_pass_when_state_changed(
        self,
    ) -> None:
        """Executor state/in-progress → state/handoff → pass"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_executor_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/handoff"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=200,
                branch="task/issue-200",
                actor="agent:run",
                role="executor",
                before_state_label="state/in-progress",
            )

        mock_block.assert_not_called()
