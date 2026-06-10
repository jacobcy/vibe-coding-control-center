"""Tests for reviewer role audit artifact helpers and dispatch."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


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
                "vibe3.services.shared.roles.block_reviewer_noop_issue"
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
        from datetime import datetime
        from unittest.mock import patch

        from vibe3.execution.noop_gate import apply_unified_noop_gate
        from vibe3.models.verdict import VerdictRecord

        mock_store = MagicMock()
        mock_verdict = VerdictRecord(
            verdict="PASS",
            timestamp=datetime.now(),
            actor="agent:review",
            role="reviewer",
            flow_branch="task/issue-303",
        )
        flow_state = {
            "latest_verdict": mock_verdict,
            "audit_ref": "audit.md",
        }

        with (
            patch("vibe3.clients.github_client.GitHubClient") as mock_gh,
            patch(
                "vibe3.services.shared.roles.block_reviewer_noop_issue"
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
                flow_state=flow_state,
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


class TestDispatchAsyncManualReviewWorktreeRequirement:
    """_dispatch_async_manual_review must set worktree_requirement=PERMANENT."""

    def test_sets_worktree_requirement_permanent(self) -> None:
        """ExecutionRequest must include worktree_requirement=PERMANENT."""
        from vibe3.execution.role_contracts import WorktreeRequirement

        with (
            patch(
                "vibe3.execution.issue_role_support.resolve_orchestra_repo_root",
                return_value=Path("/fake/repo"),
            ),
            patch("vibe3.roles.review.load_orchestra_config"),
            patch("vibe3.clients.sqlite_client.SQLiteClient"),
            patch("vibe3.roles.review.ExecutionCoordinator") as mock_coord_cls,
        ):
            mock_coord = MagicMock()
            mock_coord.dispatch_execution.return_value = MagicMock(launched=True)
            mock_coord_cls.return_value = mock_coord

            from vibe3.models import ReviewRequest, ReviewScope
            from vibe3.roles.review import _dispatch_async_manual_review

            request = ReviewRequest(
                scope=ReviewScope(kind="base", base_branch="main"),
            )
            _dispatch_async_manual_review(
                request=request,
                branch="dev/issue-42",
                issue_number=42,
                pr_number=None,
                instructions="review this",
            )

            exec_request = mock_coord.dispatch_execution.call_args[0][0]
            assert exec_request.worktree_requirement == WorktreeRequirement.PERMANENT
            assert exec_request.cwd is None
            assert exec_request.repo_path == "/fake/repo"
