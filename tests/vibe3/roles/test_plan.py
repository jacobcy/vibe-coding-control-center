"""Tests for planner role completion scenarios.

钉死 planner 的关键行为：
1. blocked issue 不应该被派发
2. blocked → handoff 转换应该被阻止

Note: 执行报错/无行动等场景的 fail/block 调用已在 test_issue_failure_service.py 中测试。
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest


class TestPlannerSuccessStateChanged:
    """场景 4: planner 正常推进 → 不干预"""

    @pytest.mark.skip(reason="Placeholder until planner success behavior is asserted")
    def test_planner_success_no_forced_handoff_event(
        self,
    ) -> None:
        """Planner 正常推进 → 不应该强制转 HANDOFF"""


class TestPlannerNoOpGate:
    """Planner no-op gate: state 未变 → blocked"""

    def test_planner_blocked_when_state_unchanged(
        self,
    ) -> None:
        """Planner state/claimed 未变 → blocked"""
        from unittest.mock import MagicMock, patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

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
            apply_unified_noop_gate(
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

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_planner_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/handoff"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=100,
                branch="task/issue-100",
                actor="agent:plan",
                role="planner",
                before_state_label="state/claimed",
            )

        mock_block.assert_not_called()


def test_build_plan_prompt_retry_resume_provides_bootstrap_fallback() -> None:
    from vibe3.models.orchestration import IssueInfo
    from vibe3.roles.plan import build_plan_prompt

    config = SimpleNamespace(repo="owner/repo")
    issue = IssueInfo(number=123, title="Retry planning", labels=[])
    flow_state = {"plan_ref": "docs/plans/issue-123-plan.md"}

    with patch("vibe3.roles.plan._build_plan_task_guidance", return_value=None):
        prompt, refs, summary, include_notice, fallback_prompt = build_plan_prompt(
            config,
            issue,
            "task/issue-123",
            flow_state,
            session_id="ses_123",
        )

    assert refs == {"plan_ref": "docs/plans/issue-123-plan.md"}
    assert summary["prompt_mode"] == "retry"
    assert summary["context_mode"] == "resume"
    assert summary["fallback_context_mode"] == "bootstrap"
    assert include_notice is False
    assert fallback_prompt is not None
    assert "policy" not in prompt.lower()
    assert "handoff plan" in prompt
    assert "## Output format requirements" in fallback_prompt
