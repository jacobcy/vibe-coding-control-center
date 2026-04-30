"""Tests for reviewer role audit artifact helpers."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


class TestReviewerFailed:
    """场景 1: reviewer 执行报错 -> state/failed"""

    def test_reviewer_failed_calls_fail_reviewer_issue(
        self,
    ) -> None:
        """Reviewer 执行报错 -> 调用 fail_reviewer_issue"""
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
                "fail",  # action
                "review execution crashed",  # reason
                "agent:review",  # actor
            )


class TestReviewerBlockedNoAuditRef:
    """场景 2: reviewer 无行动 -> state/blocked"""

    def test_reviewer_blocked_no_audit_ref_calls_block_reviewer(
        self,
    ) -> None:
        """Reviewer 无行动 -> 调用 block_reviewer_noop_issue"""
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
                "block",  # action
                "state unchanged",  # reason
                "agent:review",  # actor
            )


class TestReviewerBlockedNoStateChange:
    """场景 3: reviewer 有产出但无推进 -> state/blocked"""

    def test_reviewer_blocked_no_state_change_calls_block_reviewer(
        self,
    ) -> None:
        """Reviewer 有 audit_ref 但 state 未变 -> block"""
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
                "no state change",  # reason
                "agent:review",
            )


class TestReviewerNoOpGate:
    """场景 4: reviewer state 未变 -> blocked"""

    def test_reviewer_blocked_when_state_unchanged(
        self,
    ) -> None:
        """Reviewer state/review 未变 -> blocked"""
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
        """Reviewer state/review -> state/handoff -> pass"""
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
                "labels": [{"name": "state/handoff"}],
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

        mock_block.assert_not_called()


class TestFinalizeReviewOutput:
    """finalize_review_output is a pure passive reader.

    It does NOT parse review output, create artifacts, or call record_audit.
    It only reads existing audit_ref and verdict from flow state.
    """

    @patch("vibe3.roles.review_helpers._load_existing_verdict")
    @patch("vibe3.roles.review_helpers._load_existing_audit_ref")
    def test_returns_existing_audit_and_verdict(
        self,
        mock_load_audit_ref: MagicMock,
        mock_load_verdict: MagicMock,
    ) -> None:
        """When agent wrote both audit_ref and verdict, return them."""
        from vibe3.roles.review_helpers import finalize_review_output

        mock_load_audit_ref.return_value = "docs/reports/issue-42-audit.md"
        mock_load_verdict.return_value = "MAJOR"

        audit_ref, verdict = finalize_review_output(
            review_output="anything",
            branch="task/issue-42",
            actor="claude/opus",
        )

        assert audit_ref == "docs/reports/issue-42-audit.md"
        assert verdict == "MAJOR"

    @patch("vibe3.roles.review_helpers._load_existing_verdict")
    @patch("vibe3.roles.review_helpers._load_existing_audit_ref")
    def test_returns_empty_when_no_audit(
        self,
        mock_load_audit_ref: MagicMock,
        mock_load_verdict: MagicMock,
    ) -> None:
        """When agent wrote nothing, return empty string and UNKNOWN."""
        from vibe3.roles.review_helpers import finalize_review_output

        mock_load_audit_ref.return_value = None
        mock_load_verdict.return_value = None

        audit_ref, verdict = finalize_review_output(
            review_output="anything",
            branch="task/issue-42",
            actor="claude/opus",
        )

        assert audit_ref == ""
        assert verdict == "UNKNOWN"

    @patch("vibe3.roles.review_helpers._load_existing_verdict")
    @patch("vibe3.roles.review_helpers._load_existing_audit_ref")
    def test_no_side_effects(
        self,
        mock_load_audit_ref: MagicMock,
        mock_load_verdict: MagicMock,
    ) -> None:
        """finalize_review_output must not write anything."""
        from vibe3.roles.review_helpers import finalize_review_output

        mock_load_audit_ref.return_value = "docs/reports/issue-42-audit.md"
        mock_load_verdict.return_value = "PASS"

        finalize_review_output(
            review_output="anything",
            branch="task/issue-42",
            actor="claude/opus",
        )

        # Only two read calls, no writes
        mock_load_audit_ref.assert_called_once_with("task/issue-42")
        mock_load_verdict.assert_called_once_with("task/issue-42")


def test_build_issue_review_request_retry_resume_provides_bootstrap_fallback() -> None:
    from vibe3.models.orchestration import IssueInfo
    from vibe3.roles.review import build_issue_review_request

    issue = IssueInfo(number=301, title="Retry review", labels=[])
    config = SimpleNamespace(
        repo="owner/repo",
        review=SimpleNamespace(review_prompt=None),
    )
    flow_state = {
        "report_ref": "docs/reports/issue-301-report.md",
        "audit_ref": "docs/reports/issue-301-audit.md",
    }

    request = build_issue_review_request(
        issue,
        branch="task/issue-301",
        sync=True,
        config=config,
        session_id="ses_301",
        options=object(),
        dry_run=True,
        flow_state=flow_state,
    )

    assert request.refs["report_ref"] == "docs/reports/issue-301-report.md"
    assert request.refs["audit_ref"] == "docs/reports/issue-301-audit.md"
    assert request.dry_run_summary["prompt_mode"] == "retry"
    assert request.dry_run_summary["context_mode"] == "resume"
    assert request.dry_run_summary["fallback_context_mode"] == "bootstrap"
    assert request.include_global_notice is False
    assert request.fallback_prompt is not None
