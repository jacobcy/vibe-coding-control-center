"""Tests for unified flow recovery service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.exceptions import UserError
from vibe3.services.flow.recovery import (
    FlowRecoveryService,
    RecoveryAction,
)


def _make_service(
    *,
    worktree_path=None,
    flow_state=None,
    ref_exists=True,
    branch_exists=True,
):
    store = MagicMock()
    store.get_flow_state.return_value = flow_state or {}
    git = MagicMock()
    git.find_worktree_path_for_branch.return_value = worktree_path
    git.branch_exists.return_value = branch_exists
    github = MagicMock()
    return FlowRecoveryService(store=store, git_client=git, github_client=github)


class TestClassifyRecovery:
    def test_healthy_flow_returns_resume_only(self):
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={"worktree_path": "/wt/task/issue-1"},
        )
        action, _ = svc.classify("task/issue-1")
        assert action == RecoveryAction.RESUME_ONLY

    def test_placeholder_flow_classify_returns_resume_only(self):
        """Placeholder flow (blocked + no branch) should classify as RESUME_ONLY."""
        svc = _make_service(
            worktree_path=None,
            flow_state={"flow_status": "blocked"},
            branch_exists=False,
        )
        action, consistency = svc.classify("task/issue-1")
        assert action == RecoveryAction.RESUME_ONLY
        assert consistency is None  # No consistency check result

    def test_missing_worktree_returns_rebuild(self):
        svc = _make_service(worktree_path=None, flow_state={})
        action, _ = svc.classify("task/issue-1")
        assert action == RecoveryAction.REBUILD

    def test_missing_recorded_worktree_returns_fix_and_resume(self):
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={},  # no worktree_path recorded
        )
        action, _ = svc.classify("task/issue-1")
        assert action == RecoveryAction.FIX_AND_RESUME

    def test_missing_artifact_classifies_as_artifact_blocked(self):
        """A missing recorded artifact in a healthy worktree classifies as
        ARTIFACT_BLOCKED, never REBUILD (spec 012 US2 SC-002 — a missing
        artifact never causes automatic destruction of a healthy worktree)."""
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={
                "worktree_path": "/wt/task/issue-1",
                "plan_ref": "docs/plans/missing.md",
            },
        )
        with patch(
            "vibe3.services.flow.consistency.check_ref_exists",
            return_value=("docs/plans/missing.md", False),
        ):
            action, consistency = svc.classify("task/issue-1")
        assert action == RecoveryAction.ARTIFACT_BLOCKED
        assert consistency is not None
        assert consistency.ref_field == "plan_ref"


class TestRecover:
    def test_manual_resume_clears_blocked_state(self):
        """When scene is healthy, recover_manual() invokes manual_resume."""
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={"worktree_path": "/wt/task/issue-1"},
        )
        with patch(
            "vibe3.services.flow.blocked_state_service.BlockedStateService"
        ) as mock_cls:
            mock_cls.return_value.manual_resume.return_value = MagicMock(success=True)
            result = svc.recover_manual(
                branch="task/issue-1",
                issue_number=1,
                reason="manual resume",
            )
        assert result.success
        mock_cls.return_value.manual_resume.assert_called_once()

    def test_auto_fix_and_resume_backfills_then_evaluates(self):
        """Auto path: apply cheap fix, then evaluate auto eligibility."""
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={},
        )
        with patch(
            "vibe3.services.flow.blocked_state_service.BlockedStateService"
        ) as mock_cls:
            from vibe3.services.flow.blocked_state_types import (
                AutoResumeDecision,
                AutoResumeReasonCode,
                AutoResumeVerdict,
            )

            mock_cls.return_value.evaluate_auto_eligibility.return_value = (
                AutoResumeDecision(
                    verdict=AutoResumeVerdict.NOT_ELIGIBLE,
                    reason_code=AutoResumeReasonCode.HUMAN_REASON_PRESENT,
                    issue_number=1,
                    branch="task/issue-1",
                    truth_snapshot=None,
                )
            )
            result = svc.recover_auto(
                branch="task/issue-1",
                issue_number=1,
                reason="auto recover",
            )
        assert result.action == RecoveryAction.FIX_AND_RESUME
        assert result.success
        svc.store.update_flow_state.assert_any_call(
            "task/issue-1", worktree_path=str(Path("/wt/task/issue-1"))
        )
        mock_cls.return_value.evaluate_auto_eligibility.assert_called_once()

    def test_rebuild_auto_does_full_rebuild_then_evaluates(self):
        svc = _make_service(worktree_path=None, flow_state={})
        with (
            patch.object(svc, "_do_rebuild") as mock_rebuild,
            patch(
                "vibe3.services.flow.blocked_state_service.BlockedStateService"
            ) as mock_cls,
        ):
            from vibe3.services.flow.blocked_state_types import (
                AutoResumeDecision,
                AutoResumeReasonCode,
                AutoResumeVerdict,
            )

            decision = AutoResumeDecision(
                verdict=AutoResumeVerdict.NOT_ELIGIBLE,
                reason_code=AutoResumeReasonCode.DEPENDENCY_OPEN,
                issue_number=1,
                branch="task/issue-1",
                truth_snapshot=None,
            )
            mock_cls.return_value.evaluate_auto_eligibility.return_value = decision
            result = svc.recover_auto(
                branch="task/issue-1",
                issue_number=1,
                reason="health check",
            )
        assert result.action == RecoveryAction.REBUILD
        assert result.success
        mock_rebuild.assert_called_once()
        mock_cls.return_value.evaluate_auto_eligibility.assert_called_once()

    def test_rebuild_manual_raises_for_user_guidance(self):
        """Manual path (task resume) should NOT auto-rebuild; guide user."""
        svc = _make_service(worktree_path=None, flow_state=None)
        with pytest.raises(Exception, match="flow rebuild"):
            svc.recover_manual(
                branch="task/issue-1",
                issue_number=1,
                reason="manual",
            )

    def test_missing_artifact_manual_raises_to_guide_rebind(self):
        """Manual recovery of a missing artifact raises UserError guiding
        rebind/regeneration — it must NOT rebuild the healthy scene."""
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={
                "worktree_path": "/wt/task/issue-1",
                "plan_ref": "docs/plans/missing.md",
            },
        )
        with patch(
            "vibe3.services.flow.consistency.check_ref_exists",
            return_value=("docs/plans/missing.md", False),
        ):
            with pytest.raises(UserError, match="Artifact repair blocker"):
                svc.recover(
                    branch="task/issue-1",
                    issue_number=1,
                    reason="manual resume",
                    auto=False,
                )

    def test_missing_artifact_auto_keeps_blocked_without_rebuild(self):
        """Auto recovery of a missing artifact neither rebuilds nor clears
        blocked markers — the scene stays blocked waiting for artifact repair."""
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={
                "worktree_path": "/wt/task/issue-1",
                "plan_ref": "docs/plans/missing.md",
            },
        )
        with (
            patch(
                "vibe3.services.flow.consistency.check_ref_exists",
                return_value=("docs/plans/missing.md", False),
            ),
            patch.object(svc, "_do_rebuild") as mock_rebuild,
            patch.object(svc, "_do_resume") as mock_resume,
        ):
            result = svc.recover(
                branch="task/issue-1",
                issue_number=1,
                reason="auto recovery",
                auto=True,
            )
        mock_rebuild.assert_not_called()
        mock_resume.assert_not_called()
        assert result.action == RecoveryAction.ARTIFACT_BLOCKED
        assert not result.success

    def test_auto_rebuild_fails_when_rebuilt_worktree_is_missing(self):
        svc = _make_service(worktree_path=None, flow_state={})
        svc.git_client.branch_exists.return_value = True
        svc.git_client.find_worktree_path_for_branch.return_value = None

        with (
            patch(
                "vibe3.services.issue.context.load_issue_info",
                return_value=MagicMock(number=1),
            ),
            patch("vibe3.services.flow.rebuild.FlowRebuildUsecase") as rebuild_cls,
            pytest.raises(RuntimeError, match="Rebuild postcondition failed"),
        ):
            rebuild_cls.return_value.rebuild_issue_flow.side_effect = RuntimeError(
                "Rebuild postcondition failed for task/issue-1: "
                "git worktree not registered for branch: task/issue-1"
            )

            svc._do_rebuild(
                "task/issue-1",
                1,
                "health check",
                ensure_worktree=True,
            )

        rebuild_cls.return_value.rebuild_issue_flow.assert_called_once()
