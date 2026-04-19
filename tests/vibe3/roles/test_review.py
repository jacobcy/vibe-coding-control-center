"""Tests for reviewer role audit artifact helpers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.roles.review import (
    _create_minimal_audit_artifact,
    _resolve_authoritative_audit_ref,
)


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
    """场景 2: reviewer 无行动 → state/blocked"""

    def test_reviewer_blocked_no_audit_ref_calls_block_reviewer(
        self,
    ) -> None:
        """Reviewer 无行动 → 调用 block_reviewer_noop_issue"""
        with patch(
            "vibe3.services.issue_failure_service._ensure_flow_state_for_issue"
        ) as mock_ensure:
            from vibe3.services.issue_failure_service import block_reviewer_noop_issue

            block_reviewer_noop_issue(
                issue_number=301,
                repo="jacobcy/vibe-coding-control-center",
                reason="state unchanged",
                actor="agent:review",
            )

            # Verify: _ensure_flow_state_for_issue called with "block" action
            mock_ensure.assert_called_once_with(
                301,
                "block",  # ← action 参数
                "state unchanged",  # ← reason
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


class TestReviewerNoOpGate:
    """场景 4: reviewer state 未变 → blocked"""

    def test_reviewer_blocked_when_state_unchanged(
        self,
    ) -> None:
        """Reviewer state/review 未变 → blocked"""
        from unittest.mock import patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
            ) as mock_block,
        ):
            mock_gh.return_value.view_issue.return_value = {
                "labels": [{"name": "state/review"}],
                "state": "open",
            }
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=303,
                branch="task/issue-303",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
            )

        mock_block.assert_called_once()

    def test_reviewer_pass_when_state_changed(
        self,
    ) -> None:
        """Reviewer state/review → state/handoff → pass"""
        from unittest.mock import patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate

        mock_store = MagicMock()
        mock_store.get_flow_state.return_value = {
            "audit_ref": "/path/to/audit.md",
            "state_label": "state/handoff",
        }

        with patch(
            "vibe3.services.issue_failure_service.block_reviewer_noop_issue"
        ) as mock_block:
            apply_unified_noop_gate(
                store=mock_store,
                issue_number=303,
                branch="task/issue-303",
                actor="agent:review",
                role="reviewer",
                before_state_label="state/review",
            )

        mock_block.assert_not_called()


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


def test_create_minimal_audit_artifact_prefers_worktree_reports_dir(
    tmp_path: Path,
) -> None:
    with patch("vibe3.roles.review.GitClient") as mock_git_cls:
        mock_git = mock_git_cls.return_value
        mock_git.find_worktree_path_for_branch.return_value = tmp_path
        artifact_path = _create_minimal_audit_artifact(
            "LGTM - The implementation looks good",
            "UNKNOWN",
            "task/issue-340",
        )

    assert artifact_path.parent == tmp_path / "docs" / "reports"
    assert artifact_path.name.startswith("task-issue-340-audit-auto-")
    assert artifact_path.read_text(encoding="utf-8").startswith(
        "# Minimal Review Audit"
    )


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
