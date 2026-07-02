"""Core API tests for manual_resume, evaluate_auto_resume, apply_auto_resume."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models import IssueState
from vibe3.services.flow.resume_api import (
    AutoResumeDecision,
    AutoResumeRejectedCode,
    apply_auto_resume,
    evaluate_auto_resume,
    manual_resume,
)


class TestEvaluateAutoResume:
    """Tests for evaluate_auto_resume (observer-only eligibility check)."""

    def test_human_reason_present_returns_not_eligible(self) -> None:
        """evaluate_auto_resume with human reason present → NOT_ELIGIBLE, HUMAN_REASON_PRESENT."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock GitHub body with human reason
            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked reason**: Manual review required

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            decision = evaluate_auto_resume(
                issue_number=123,
                branch="task/issue-123",
                github_client=MagicMock(),
            )

            assert not decision.eligible
            assert decision.rejected_code == AutoResumeRejectedCode.HUMAN_REASON_PRESENT
            assert "Manual review required" in decision.reason_detail

    def test_open_dependency_returns_not_eligible(self) -> None:
        """evaluate_auto_resume with open dependency → NOT_ELIGIBLE, DEPENDENCY_OPEN."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock GitHub body with dependency
            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            # Mock dependency resolution - dependency is OPEN
            with patch(
                "vibe3.services.flow.resume_api.DependencyResolutionService.is_dependency_resolved"
            ) as mock_resolved:
                mock_resolved.return_value = MagicMock(
                    resolved=False, github_state="open"
                )

                decision = evaluate_auto_resume(
                    issue_number=123,
                    branch="task/issue-123",
                    github_client=MagicMock(),
                )

                assert not decision.eligible
                assert decision.rejected_code == AutoResumeRejectedCode.DEPENDENCY_OPEN
                assert "456" in decision.reason_detail

    def test_github_unreadable_returns_not_eligible(self) -> None:
        """evaluate_auto_resume with unreachable GitHub → NOT_ELIGIBLE, TRUTH_UNREADABLE."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock GitHub API failure
            mock_io.github.get_issue_body.side_effect = Exception("GitHub API error")

            decision = evaluate_auto_resume(
                issue_number=123,
                branch="task/issue-123",
                github_client=MagicMock(),
            )

            assert not decision.eligible
            assert decision.rejected_code == AutoResumeRejectedCode.TRUTH_UNREADABLE
            assert "GitHub API error" in decision.reason_detail

    def test_all_deps_closed_no_reason_returns_eligible(self) -> None:
        """evaluate_auto_resume with reason absent + all deps closed → ELIGIBLE."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock GitHub body - no reason, has closed dependency
            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456, #789

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            # Mock all dependencies closed
            with patch(
                "vibe3.services.flow.resume_api.DependencyResolutionService.is_dependency_resolved"
            ) as mock_resolved:
                mock_resolved.return_value = MagicMock(
                    resolved=True, github_state="closed"
                )

                decision = evaluate_auto_resume(
                    issue_number=123,
                    branch="task/issue-123",
                    github_client=MagicMock(),
                )

                assert decision.eligible
                assert decision.rejected_code is None
                assert decision.closed_dependency_ids == (456, 789)
                assert decision.truth_snapshot != ""  # MD5 hash present

    def test_not_blocked_returns_not_eligible(self) -> None:
        """evaluate_auto_resume when issue is not blocked → NOT_ELIGIBLE, NOT_BLOCKED."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: ready

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.READY

            decision = evaluate_auto_resume(
                issue_number=123,
                branch="task/issue-123",
                github_client=MagicMock(),
            )

            assert not decision.eligible
            assert decision.rejected_code == AutoResumeRejectedCode.NOT_BLOCKED


class TestManualResume:
    """Tests for manual_resume (human-authorized clearance)."""

    def test_manual_resume_clears_reason_and_records_actor(self) -> None:
        """manual_resume clears reason and records actor/event."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock currently blocked with no dependencies
            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked reason**: Manual review needed

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED
            mock_io.write_label_state.return_value = "advanced"

            # Mock store with db_path and count_specific_pair
            mock_store = MagicMock()
            mock_store.db_path = ":memory:"
            mock_store.get_flow_state.return_value = None
            mock_store.count_specific_pair.return_value = 0
            mock_store.record_confirmed_transition.return_value = (1, 1, 1)

            result = manual_resume(
                issue_number=123,
                branch="task/issue-123",
                target_state=IssueState.READY,
                actor="cli:user",
                reason="User approved after review",
                github_client=MagicMock(),
                store=mock_store,
            )

            assert result.success
            assert result.target_state == IssueState.READY
            # Verify projection was written with cleared reason
            call_args = mock_io.write_projection.call_args
            projection = call_args[0][1]
            assert projection.blocked_reason is None
            assert projection.state == "active"

    def test_manual_resume_with_open_dep_fails_closed(self) -> None:
        """manual_resume with open dep → fail closed (no force in this scope)."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock currently blocked with open dependency
            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            # Mock dependency is OPEN
            with patch(
                "vibe3.services.flow.resume_api.DependencyResolutionService.is_dependency_resolved"
            ) as mock_resolved:
                mock_resolved.return_value = MagicMock(
                    resolved=False, github_state="open"
                )

                # Mock store with db_path and count_specific_pair
                mock_store = MagicMock()
                mock_store.db_path = ":memory:"
                mock_store.get_flow_state.return_value = None
                mock_store.count_specific_pair.return_value = 0

                result = manual_resume(
                    issue_number=123,
                    branch="task/issue-123",
                    target_state=IssueState.READY,
                    actor="cli:user",
                    reason="User wants to resume",
                    github_client=MagicMock(),
                    store=mock_store,
                )

                assert not result.success
                assert "Open dependencies remain" in result.detail
                assert "456" in result.detail

    def test_manual_resume_not_blocked_fails(self) -> None:
        """manual_resume when not blocked → fails."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: ready

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.READY

            result = manual_resume(
                issue_number=123,
                branch="task/issue-123",
                target_state=IssueState.READY,
                actor="cli:user",
                reason="User wants to resume",
                github_client=MagicMock(),
                store=MagicMock(),
            )

            assert not result.success
            assert "not blocked" in result.detail.lower()


class TestApplyAutoResume:
    """Tests for apply_auto_resume (apply eligibility decision)."""

    def test_apply_with_stale_snapshot_rejects(self) -> None:
        """apply_auto_resume with stale snapshot → reject."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock body has changed since evaluation
            mock_io.github.get_issue_body.return_value = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked reason**: New reason added

<!-- vibe3-flow-state-end -->
"""
            mock_io.read_issue_state.return_value = IssueState.BLOCKED

            # Create decision with old snapshot
            decision = AutoResumeDecision(
                eligible=True,
                issue_number=123,
                branch="task/issue-123",
                closed_dependency_ids=(),
                truth_snapshot="old_hash_that_doesnt_match",
            )

            result = apply_auto_resume(
                decision,
                github_client=MagicMock(),
                store=MagicMock(),
            )

            assert not result.success
            assert "stale" in result.detail.lower()

    def test_apply_for_existing_flow_targets_handoff(self) -> None:
        """apply_auto_resume for existing flow → handoff."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock body unchanged
            body = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked

<!-- vibe3-flow-state-end -->
"""
            mock_io.github.get_issue_body.return_value = body
            mock_io.read_issue_state.return_value = IssueState.BLOCKED
            mock_io.write_label_state.return_value = "advanced"

            # Mock existing flow
            mock_store = MagicMock()
            mock_store.db_path = ":memory:"
            mock_store.get_flow_state.return_value = {
                "branch": "task/issue-123",
                "flow_status": "blocked",
            }
            mock_store.count_specific_pair.return_value = 0
            mock_store.record_confirmed_transition.return_value = (1, 1, 1)

            # Create valid decision
            import hashlib

            decision = AutoResumeDecision(
                eligible=True,
                issue_number=123,
                branch="task/issue-123",
                closed_dependency_ids=(),
                truth_snapshot=hashlib.md5(body.encode()).hexdigest(),
            )

            result = apply_auto_resume(
                decision,
                github_client=MagicMock(),
                store=mock_store,
            )

            assert result.success
            assert result.target_state == IssueState.HANDOFF

    def test_apply_for_pre_flow_targets_ready(self) -> None:
        """apply_auto_resume for pre-flow → ready."""
        with patch("vibe3.services.flow.resume_api.BlockedStateIO") as mock_io_class:
            mock_io = MagicMock()
            mock_io_class.return_value = mock_io

            # Mock body unchanged
            body = """<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked

<!-- vibe3-flow-state-end -->
"""
            mock_io.github.get_issue_body.return_value = body
            mock_io.read_issue_state.return_value = IssueState.BLOCKED
            mock_io.write_label_state.return_value = "advanced"

            # Mock NO existing flow
            mock_store = MagicMock()
            mock_store.db_path = ":memory:"
            mock_store.get_flow_state.return_value = None
            mock_store.count_specific_pair.return_value = 0
            mock_store.record_confirmed_transition.return_value = (1, 1, 1)

            # Create valid decision
            import hashlib

            decision = AutoResumeDecision(
                eligible=True,
                issue_number=123,
                branch="task/issue-123",
                closed_dependency_ids=(),
                truth_snapshot=hashlib.md5(body.encode()).hexdigest(),
            )

            result = apply_auto_resume(
                decision,
                github_client=MagicMock(),
                store=mock_store,
            )

            assert result.success
            assert result.target_state == IssueState.READY


class TestAutoPathNoClearReason:
    """Tests that auto path has no callable API param to clear reason."""

    def test_evaluate_auto_resume_has_no_reason_param(self) -> None:
        """evaluate_auto_resume has no reason or clear_reason parameter."""
        import inspect

        sig = inspect.signature(evaluate_auto_resume)
        params = list(sig.parameters.keys())
        assert "reason" not in params
        assert "clear_reason" not in params

    def test_apply_auto_resume_has_no_reason_param(self) -> None:
        """apply_auto_resume has no reason or clear_reason parameter."""
        import inspect

        sig = inspect.signature(apply_auto_resume)
        params = list(sig.parameters.keys())
        assert "reason" not in params
        assert "clear_reason" not in params

    def test_auto_resume_decision_is_frozen(self) -> None:
        """AutoResumeDecision is frozen (immutable)."""
        decision = AutoResumeDecision(
            eligible=True,
            issue_number=123,
            branch="task/issue-123",
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            decision.eligible = False  # type: ignore[misc]
