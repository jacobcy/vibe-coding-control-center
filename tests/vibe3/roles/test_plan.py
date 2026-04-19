"""Tests for planner role completion scenarios.

钉死 planner 的 4 种场景行为：
1. 执行报错 → state/failed + failed_reason
2. 无行动 → state/blocked + blocked_reason='state unchanged'
3. 有行动但无推进 → state/blocked + blocked_reason='no state change'
4. 正常推进 → 不干预（agent 改状态）
"""

from unittest.mock import patch

from vibe3.models.orchestration import IssueState


class TestPlannerFailed:
    """场景 1: planner 执行报错 → state/failed"""

    def test_planner_failed_calls_fail_planner_issue(
        self,
    ) -> None:
        """Planner 执行报错 → 调用 fail_planner_issue"""
        mock_issue_number = 100

        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import fail_planner_issue

            fail_planner_issue(
                issue_number=mock_issue_number,
                reason="timeout after 60s",
                actor="agent:plan",
            )

            # Verify: _ensure_flow_state_for_issue called with "fail" action
            mock_ensure.assert_called_once_with(
                mock_issue_number,
                "fail",  # ← action 参数
                "timeout after 60s",  # ← reason
                "agent:plan",  # ← actor
            )


class TestPlannerBlockedNoPlanRef:
    """场景 2: planner 无行动 → state/blocked"""

    def test_planner_blocked_no_plan_ref_calls_block_planner(
        self,
    ) -> None:
        """Planner 无行动 → 调用 block_planner_noop_issue"""
        mock_issue_number = 101

        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_planner_noop_issue

            block_planner_noop_issue(
                issue_number=mock_issue_number,
                reason="state unchanged",
                actor="agent:plan",
            )

            # Verify: _ensure_flow_state_for_issue called with "block" action
            mock_ensure.assert_called_once_with(
                mock_issue_number,
                "block",  # ← action 参数
                "state unchanged",  # ← reason
                "agent:plan",  # ← actor
            )


class TestPlannerBlockedNoStateChange:
    """场景 3: planner 有产出但无推进 → state/blocked"""

    def test_planner_blocked_no_state_change_calls_block_planner(
        self,
    ) -> None:
        """Planner 有 plan_ref 但 state 未变 → block"""
        mock_issue_number = 102

        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_planner_noop_issue

            block_planner_noop_issue(
                issue_number=mock_issue_number,
                reason="no state change",
                actor="agent:plan",
            )

            # Verify: block reason
            mock_ensure.assert_called_once_with(
                mock_issue_number,
                "block",
                "no state change",  # ← reason
                "agent:plan",
            )


class TestPlannerSuccessStateChanged:
    """场景 4: planner 正常推进 → 不干预"""

    def test_planner_success_no_forced_handoff_event(
        self,
    ) -> None:
        """Planner 正常推进 → 不应该强制转 HANDOFF"""
        # This test verifies that planner success does NOT force HANDOFF
        # The actual implementation will be fixed to remove confirm_role_handoff
        # For now, we document the expected behavior
        pass  # ← Placeholder: 实际修复后添加详细测试


class TestPlannerNoProgressPolicy:
    """Planner no-progress 检测"""

    def test_planner_has_progress_with_plan_ref(
        self,
    ) -> None:
        """Planner 有 plan_ref → 有推进"""
        from vibe3.runtime.no_progress_policy import has_progress_changed

        before = {
            "state_label": IssueState.CLAIMED.to_label(),
            "comment_count": 0,
            "handoff": None,
            "refs": {},
            "issue_state": "open",
            "flow_status": "active",
        }

        after = {
            "state_label": IssueState.CLAIMED.to_label(),
            "comment_count": 1,
            "handoff": None,
            "refs": {"plan_ref": "docs/plans/issue-100-plan.md"},  # ← 有 plan_ref
            "issue_state": "open",
            "flow_status": "active",
        }

        has_progress = has_progress_changed(
            before=before,
            after=after,
            expected_ref="plan_ref",  # ← 检查 plan_ref
        )

        assert has_progress is True  # ← 有推进（plan_ref 变化）

    def test_planner_no_progress_without_plan_ref(
        self,
    ) -> None:
        """Planner 无 plan_ref → 无推进"""
        from vibe3.runtime.no_progress_policy import has_progress_changed

        before = {
            "state_label": IssueState.CLAIMED.to_label(),
            "comment_count": 0,
            "handoff": None,
            "refs": {},
            "issue_state": "open",
            "flow_status": "active",
        }

        after = {
            "state_label": IssueState.CLAIMED.to_label(),
            "comment_count": 2,
            "handoff": None,
            "refs": {},  # ← 无 plan_ref
            "issue_state": "open",
            "flow_status": "active",
        }

        has_progress = has_progress_changed(
            before=before,
            after=after,
            expected_ref="plan_ref",  # ← 检查 plan_ref
        )

        assert has_progress is False  # ← 无推进（plan_ref 缺失）


class TestPlannerNoOpGate:
    """Planner no-op gate: state 未变 → blocked"""

    def test_planner_blocked_when_state_unchanged(
        self,
    ) -> None:
        """Planner state/claimed 未变 → blocked"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.codeagent_runner import (
            _apply_unified_noop_gate,
        )

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/claimed"}],
                "state": "open",
            }
            _apply_unified_noop_gate(
                store=mock_store,
                issue_number=100,
                branch="task/issue-100",
                actor="agent:plan",
                role="planner",
                before_state_label="state/claimed",
            )

        mock_block.assert_called_once()

    def test_planner_pass_when_state_changed(
        self,
    ) -> None:
        """Planner state/claimed → state/handoff → pass"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.codeagent_runner import (
            _apply_unified_noop_gate,
        )

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {
            "plan_ref": "/path/to/plan.md",
            "state_label": "state/handoff",
        }

        with patch(
            "vibe3.services.issue_failure_service.block_planner_noop_issue"
        ) as mock_block:
            _apply_unified_noop_gate(
                store=mock_store,
                issue_number=100,
                branch="task/issue-100",
                actor="agent:plan",
                role="planner",
                before_state_label="state/claimed",
            )

        mock_block.assert_not_called()
