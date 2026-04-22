"""Tests for manager role dispatching and state transition behavior.

钉死 manager 的关键行为：
1. blocked issue 不应该被派发
2. blocked → handoff 转换应该被阻止
3. blocked_reason 字段正确写入
"""

from unittest.mock import Mock, patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService
from vibe3.roles.manager import HANDOFF_MANAGER_ROLE, MANAGER_ROLE


class TestManagerBlockedIssueNotDispatched:
    """blocked issue 不应该被派发"""

    def test_blocked_issue_skipped_by_ready_dispatcher(
        self,
    ) -> None:
        """Dispatcher 在 state/ready 时应该跳过 blocked issue"""
        # Setup: issue with state/blocked label
        blocked_issue_data = {
            "number": 303,
            "title": "Test blocked issue",
            "labels": [{"name": IssueState.BLOCKED.to_label()}],
            "state": "open",
        }

        ready_issue_data = {
            "number": 200,
            "title": "Test ready issue",
            "labels": [{"name": IssueState.READY.to_label()}],
            "state": "open",
        }

        # Mock GitHub client
        with patch("vibe3.clients.github_client.GitHubClient") as mock_github_class:
            mock_github = mock_github_class.return_value
            mock_github.list_issues.return_value = [
                blocked_issue_data,
                ready_issue_data,
            ]

            # Mock config with max_concurrent_flows
            mock_config = Mock()
            mock_config.max_concurrent_flows = 4  # ← 必须设置

            # Mock SessionRegistryService (required)
            mock_registry = Mock()

            # Create dispatcher for READY state
            dispatcher = StateLabelDispatchService(
                config=mock_config,
                github=mock_github,
                role_def=MANAGER_ROLE,
                registry=mock_registry,  # ← 注入 registry
            )

            # Collect ready issues
            import asyncio

            ready_issues = asyncio.run(dispatcher.collect_ready_issues())

        # Verify: blocked issue not in ready list
        assert 303 not in [issue.number for issue in ready_issues]
        assert 200 in [issue.number for issue in ready_issues]

    def test_blocked_issue_skipped_by_handoff_dispatcher(
        self,
    ) -> None:
        """Dispatcher 在 state/handoff 时也应该跳过 blocked issue"""
        blocked_issue_data = {
            "number": 303,
            "title": "Test blocked issue",
            "labels": [{"name": IssueState.BLOCKED.to_label()}],
            "state": "open",
        }

        handoff_issue_data = {
            "number": 201,
            "title": "Test handoff issue",
            "labels": [{"name": IssueState.HANDOFF.to_label()}],
            "state": "open",
        }

        with patch("vibe3.clients.github_client.GitHubClient") as mock_github_class:
            mock_github = mock_github_class.return_value
            mock_github.list_issues.return_value = [
                blocked_issue_data,
                handoff_issue_data,
            ]

            # Mock config with max_concurrent_flows
            mock_config = Mock()
            mock_config.max_concurrent_flows = 4  # ← 必须设置

            # Mock SessionRegistryService (required)
            mock_registry = Mock()

            # Create dispatcher for HANDOFF state
            dispatcher = StateLabelDispatchService(
                config=mock_config,
                github=mock_github,
                role_def=HANDOFF_MANAGER_ROLE,
                registry=mock_registry,  # ← 注入 registry
            )

            import asyncio

            ready_issues = asyncio.run(dispatcher.collect_ready_issues())

        # Verify: blocked issue not dispatched even in HANDOFF trigger
        assert 303 not in [issue.number for issue in ready_issues]
        assert 201 in [issue.number for issue in ready_issues]


class TestManagerBlockedToHandoffTransitionBlocked:
    """blocked → handoff 转换应该被阻止"""

    def test_blocked_to_handoff_forbidden_without_force(
        self,
    ) -> None:
        """ALLOWED_TRANSITIONS 应该拒绝 blocked → handoff"""
        from vibe3.domain.state_machine import validate_transition
        from vibe3.exceptions import InvalidTransitionError

        # Try blocked → handoff
        with pytest.raises(InvalidTransitionError):
            validate_transition(
                from_state=IssueState.BLOCKED,
                to_state=IssueState.HANDOFF,
                force=False,  # ← 不强制
            )

    def test_blocked_to_handoff_allowed_with_force(
        self,
    ) -> None:
        """手动 resume 命令可以用 force=True 绕过"""
        from vibe3.domain.state_machine import validate_transition

        # Try blocked → handoff with force=True
        validate_transition(
            from_state=IssueState.BLOCKED,
            to_state=IssueState.HANDOFF,
            force=True,  # ← 强制绕过（用于手动命令）
        )


class TestManagerBlockedReasonWriting:
    """blocked_reason 字段写入"""

    def test_manager_blocked_calls_ensure_flow_state(
        self,
    ) -> None:
        """Manager blocked 应该调用 _ensure_flow_state_for_issue"""
        mock_issue_number = 305

        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_manager_noop_issue

            block_manager_noop_issue(
                issue_number=mock_issue_number,
                repo="jacobcy/vibe-coding-control-center",
                reason="manager 本轮未产生状态迁移",
                actor="test-backend/test-model",
            )

            # Verify: _ensure_flow_state_for_issue called with "block" action
            mock_ensure.assert_called_once_with(
                mock_issue_number,
                "block",  # ← action 参数
                "manager 本轮未产生状态迁移",  # ← reason
                "test-backend/test-model",  # ← actor (透传)
            )
