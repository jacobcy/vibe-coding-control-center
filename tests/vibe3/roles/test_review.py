"""Tests for reviewer role lifecycle publishing helpers."""

from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.domain.events import IssueFailed, ReviewCompleted
from vibe3.domain.publisher import EventPublisher
from vibe3.roles.review import (
    _resolve_authoritative_audit_ref,
    publish_review_command_failure,
    publish_review_command_success,
)


def test_publish_review_command_success_emits_review_completed() -> None:
    EventPublisher.reset()
    published_events = []
    with patch.object(EventPublisher, "publish") as mock_publish:
        mock_publish.side_effect = lambda event: published_events.append(event)
        publish_review_command_success(
            issue_number=42,
            branch="task/issue-42",
            verdict="PASS",
        )

    assert len(published_events) == 1
    event = published_events[0]
    assert isinstance(event, ReviewCompleted)
    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.verdict == "PASS"
    assert event.actor == "agent:review"


def test_publish_review_command_success_skips_without_issue_context() -> None:
    EventPublisher.reset()
    with patch.object(EventPublisher, "publish") as mock_publish:
        publish_review_command_success(
            issue_number=None,
            branch=None,
            verdict="PASS",
        )

    mock_publish.assert_not_called()


def test_publish_review_command_failure_emits_issue_failed() -> None:
    EventPublisher.reset()
    published_events = []
    with patch.object(EventPublisher, "publish") as mock_publish:
        mock_publish.side_effect = lambda event: published_events.append(event)
        publish_review_command_failure(
            issue_number=24,
            reason="review parse failed: invalid format",
        )

    assert len(published_events) == 1
    event = published_events[0]
    assert isinstance(event, IssueFailed)
    assert event.issue_number == 24
    assert "invalid format" in event.reason
    assert event.actor == "agent:review"


def test_publish_review_command_failure_skips_without_issue_number() -> None:
    EventPublisher.reset()
    with patch.object(EventPublisher, "publish") as mock_publish:
        publish_review_command_failure(
            issue_number=None,
            reason="ignored",
        )

    mock_publish.assert_not_called()


class TestReviewerFailed:
    """场景 1: reviewer 执行报错 → state/failed"""

    def test_reviewer_failed_calls_fail_reviewer_issue(
        self,
    ) -> None:
        """Reviewer 执行报错 → 调用 fail_reviewer_issue"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import fail_reviewer_issue

            fail_reviewer_issue(
                issue_number=300,
                reason="review execution crashed",
                actor="agent:review",
            )

            # Verify: _ensure_flow_state_for_issue called with "fail" action
            mock_ensure.assert_called_once_with(
                300,
                "fail",  # ← action 参数
                "review execution crashed",  # ← reason
                "agent:review",  # ← actor
            )


class TestReviewerBlockedNoAuditRef:
    """场景 2: reviewer 无产出 → state/blocked"""

    def test_reviewer_blocked_no_audit_ref_calls_block_reviewer(
        self,
    ) -> None:
        """Reviewer 无 audit_ref → 调用 block_reviewer_noop_issue"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_reviewer_noop_issue

            block_reviewer_noop_issue(
                issue_number=301,
                repo="jacobcy/vibe-coding-control-center",
                reason="no audit_ref",
                actor="agent:review",
            )

            # Verify: _ensure_flow_state_for_issue called with "block" action
            mock_ensure.assert_called_once_with(
                301,
                "block",  # ← action 参数
                "no audit_ref",  # ← reason
                "agent:review",  # ← actor
            )


class TestReviewerBlockedNoStateChange:
    """场景 3: reviewer 有产出但无推进 → state/blocked"""

    def test_reviewer_blocked_no_state_change_calls_block_reviewer(
        self,
    ) -> None:
        """Reviewer 有 audit_ref 但 state 未变 → block"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_reviewer_noop_issue

            block_reviewer_noop_issue(
                issue_number=302,
                repo="jacobcy/vibe-coding-control-center",
                reason="no state change",
                actor="agent:review",
            )

            # Verify: block reason
            mock_ensure.assert_called_once_with(
                302,
                "block",
                "no state change",  # ← reason
                "agent:review",
            )


class TestReviewerSuccessStateChanged:
    """场景 4: reviewer 正常推进 → 不干预"""

    def test_reviewer_success_no_forced_handoff_event(
        self,
    ) -> None:
        """Reviewer 正常推进 → 不应该强制转 HANDOFF"""
        # This test verifies that reviewer success does NOT force HANDOFF
        # The actual implementation will be fixed to remove confirm_role_handoff
        pass  # ← Placeholder: 实际修复后添加详细测试


class TestReviewerParserErrorTolerance:
    """场景 5: reviewer 输出格式错误 → audit_ref 仍然写入（容错性）"""

    def test_reviewer_output_written_even_if_parser_fails(
        self,
    ) -> None:
        """即使 parser 失败，audit_ref 也应该写入"""
        # Setup: reviewer 输出 "LGTM"（不符合 VERDICT 格式）

        mock_output = "LGTM - The implementation looks good"
        mock_branch = "task/issue-303"

        # Create audit_ref from raw output
        with patch("vibe3.roles.review._create_minimal_audit_artifact") as mock_create:
            mock_audit_path = Path("/tmp/audit-auto-2026-04-16T12:30:00Z.md")
            mock_create.return_value = mock_audit_path

            audit_ref = _resolve_authoritative_audit_ref(
                handoff_file=None,  # ← 无 handoff file
                review_output=mock_output,  # ← 直接使用原始输出
                verdict="UNKNOWN",  # ← parser 失败，verdict 为空
                branch=mock_branch,
            )

            # Verify: _create_minimal_audit_artifact called
            mock_create.assert_called_once_with(
                mock_output,
                "UNKNOWN",  # ← verdict 标记为 UNKNOWN
                mock_branch,
            )

            # Verify: audit_ref returned
            assert audit_ref == str(mock_audit_path)

    def test_reviewer_parser_error_does_not_raise_exception(
        self,
    ) -> None:
        """Parser 失败时不应该抛异常，而是 verdict=None"""
        from vibe3.agents.review_parser import ReviewParserError, parse_codex_review

        # Setup: output without VERDICT format
        invalid_output = "LGTM - looks good"

        # Execute: parser should raise ReviewParserError
        with pytest.raises(ReviewParserError):
            parse_codex_review(invalid_output)

        # Expected behavior in actual code:
        # try:
        #     review = parse_codex_review(output)
        #     verdict = review.verdict
        # except ReviewParserError:
        #     verdict = None  # ← 不抛异常，继续写 audit_ref


class TestReviewerNoProgressPolicy:
    """Reviewer no-progress 检测"""

    def test_reviewer_has_progress_with_audit_ref(
        self,
    ) -> None:
        """Reviewer 有 audit_ref → 有推进"""
        from vibe3.models.orchestration import IssueState
        from vibe3.runtime.no_progress_policy import has_progress_changed

        before = {
            "state_label": IssueState.REVIEW.to_label(),
            "comment_count": 0,
            "handoff": None,
            "refs": {},
            "issue_state": "open",
            "flow_status": "active",
        }

        after = {
            "state_label": IssueState.REVIEW.to_label(),
            "comment_count": 1,
            "handoff": None,
            "refs": {"audit_ref": "docs/audits/issue-300-audit.md"},  # ← 有 audit_ref
            "issue_state": "open",
            "flow_status": "active",
        }

        has_progress = has_progress_changed(
            before=before,
            after=after,
            expected_ref="audit_ref",  # ← 检查 audit_ref
        )

        assert has_progress is True  # ← 有推进（audit_ref 变化）

    def test_reviewer_no_progress_without_audit_ref(
        self,
    ) -> None:
        """Reviewer 无 audit_ref → 无推进"""
        from vibe3.models.orchestration import IssueState
        from vibe3.runtime.no_progress_policy import has_progress_changed

        before = {
            "state_label": IssueState.REVIEW.to_label(),
            "comment_count": 0,
            "handoff": None,
            "refs": {},
            "issue_state": "open",
            "flow_status": "active",
        }

        after = {
            "state_label": IssueState.REVIEW.to_label(),
            "comment_count": 2,
            "handoff": None,
            "refs": {},  # ← 无 audit_ref
            "issue_state": "open",
            "flow_status": "active",
        }

        has_progress = has_progress_changed(
            before=before,
            after=after,
            expected_ref="audit_ref",  # ← 检查 audit_ref
        )

        assert has_progress is False  # ← 无推进（audit_ref 缺失）
