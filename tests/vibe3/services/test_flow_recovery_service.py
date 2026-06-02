"""Tests for unified flow recovery service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.services.flow_recovery_service import (
    FlowRecoveryService,
    RecoveryAction,
)


def _make_service(
    *,
    worktree_path=None,
    flow_state=None,
    ref_exists=True,
):
    store = MagicMock()
    store.get_flow_state.return_value = flow_state or {}
    git = MagicMock()
    git.find_worktree_path_for_branch.return_value = worktree_path
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

    def test_missing_ref_returns_rebuild(self):
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={
                "worktree_path": "/wt/task/issue-1",
                "plan_ref": "docs/plans/missing.md",
            },
        )
        with patch(
            "vibe3.services.flow_consistency_check.check_ref_exists",
            return_value=("docs/plans/missing.md", False),
        ):
            action, _ = svc.classify("task/issue-1")
        assert action == RecoveryAction.REBUILD


class TestRecover:
    def test_resume_only_clears_blocked_state(self):
        """When scene is healthy, recover() just clears blocked markers."""
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={"worktree_path": "/wt/task/issue-1"},
        )
        with patch.object(svc, "_do_resume") as mock_resume:
            result = svc.recover(
                branch="task/issue-1",
                issue_number=1,
                reason="manual resume",
                auto=False,
            )
        assert result.action == RecoveryAction.RESUME_ONLY
        assert result.success
        mock_resume.assert_called_once()

    def test_fix_and_resume_backfills_then_clears(self):
        svc = _make_service(
            worktree_path=Path("/wt/task/issue-1"),
            flow_state={},
        )
        with patch.object(svc, "_do_resume") as mock_resume:
            result = svc.recover(
                branch="task/issue-1",
                issue_number=1,
                reason="auto recover",
                auto=True,
            )
        assert result.action == RecoveryAction.FIX_AND_RESUME
        assert result.success
        # Verify backfill happened
        svc.store.update_flow_state.assert_any_call(
            "task/issue-1", worktree_path=str(Path("/wt/task/issue-1"))
        )
        mock_resume.assert_called_once()

    def test_rebuild_auto_does_full_rebuild_then_resume(self):
        svc = _make_service(worktree_path=None, flow_state={})
        with (
            patch.object(svc, "_do_rebuild") as mock_rebuild,
            patch.object(svc, "_do_resume") as mock_resume,
        ):
            result = svc.recover(
                branch="task/issue-1",
                issue_number=1,
                reason="health check",
                auto=True,
            )
        assert result.action == RecoveryAction.REBUILD
        assert result.success
        mock_rebuild.assert_called_once()
        mock_resume.assert_called_once()

    def test_rebuild_manual_raises_for_user_guidance(self):
        """Manual path (task resume) should NOT auto-rebuild; guide user."""
        svc = _make_service(worktree_path=None, flow_state={})
        with pytest.raises(Exception, match="flow rebuild"):
            svc.recover(
                branch="task/issue-1",
                issue_number=1,
                reason="manual",
                auto=False,
            )

    def test_auto_rebuild_fails_when_rebuilt_worktree_is_missing(self):
        svc = _make_service(worktree_path=None, flow_state={})
        svc.git_client.branch_exists.return_value = True
        svc.git_client.find_worktree_path_for_branch.return_value = None

        with (
            patch(
                "vibe3.services.issue_context_loader.load_issue_info",
                return_value=MagicMock(number=1),
            ),
            patch(
                "vibe3.services.flow_rebuild_usecase.FlowRebuildUsecase"
            ) as rebuild_cls,
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
