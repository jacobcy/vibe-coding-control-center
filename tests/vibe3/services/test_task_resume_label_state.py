"""Tests for reset_issue_to_ready with --label flag state transitions."""

from unittest.mock import MagicMock, patch

import pytest

from tests.vibe3.services.conftest import _make_operations
from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState


def test_reset_issue_to_ready_with_label_keeps_worktree() -> None:
    """With --label auto, should auto-infer target state and keep worktree."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}
    operations.github_client.get_issue_body.return_value = "User content"

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    # Mock flow state for auto-inference (infer_resume_label needs FlowState)
    mock_flow_state_dict = {
        "branch": "task/issue-303",
        "flow_slug": "task/issue-303",
        "pr_ref": None,
        "audit_ref": None,
        "plan_ref": None,
        "report_ref": None,
        "latest_verdict": None,
        "worktree_path": "/tmp/task-issue-303",
    }
    operations.flow_service.store.get_flow_state.return_value = mock_flow_state_dict
    operations.flow_service.store.get_task_issue_number.return_value = 303
    operations.git_client.find_worktree_path_for_branch.return_value = (
        "/tmp/task-issue-303"
    )

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            label_state="",  # --label auto (converted to empty string internally)
        )

        # Verify: worktree NOT deleted (cleanup service not called)
        operations.git_client.remove_worktree.assert_not_called()
        operations.git_client.delete_branch.assert_not_called()

        # Verify: BlockedStateService.unblock was called
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_ready_restores_to_ready() -> None:
    """With --label ready, should restore to state/ready."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}
    operations.github_client.get_issue_body.return_value = "User content"
    operations.flow_service.store.get_task_issue_number.return_value = 303

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            label_state="ready",  # --label ready
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to READY via BlockedStateService.unblock()
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_handoff_explicit() -> None:
    """With --label handoff (explicit), should restore to state/handoff."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}
    operations.github_client.get_issue_body.return_value = "User content"
    operations.flow_service.store.get_task_issue_number.return_value = 303

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            label_state="handoff",  # --label handoff (explicit)
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to HANDOFF via BlockedStateService.unblock()
        mock_service.unblock.assert_called_once()

    # Verify: reasons cleared


def test_reset_issue_to_ready_with_label_claimed() -> None:
    """With --label claimed, should restore to state/claimed."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            label_state="claimed",  # --label claimed
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to CLAIMED via BlockedStateService.unblock()
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_in_progress() -> None:
    """With --label in-progress, should restore to state/in-progress."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            label_state="in-progress",  # --label in-progress
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to IN_PROGRESS via BlockedStateService.unblock()
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_review() -> None:
    """With --label review, should restore to state/review."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            label_state="review",  # --label review
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to REVIEW via BlockedStateService.unblock()
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_merge_ready() -> None:
    """With --label merge-ready, should restore to state/merge-ready."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            label_state="merge-ready",  # --label merge-ready
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to MERGE_READY via BlockedStateService.unblock()
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_auto_no_flow_restores_to_ready() -> None:
    """With --label auto and no flow, should restore to READY (not CLAIMED)."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    # Mock NO flow (branch is None)
    mock_flow = MagicMock()
    mock_flow.branch = None

    # get_flow_state returns None (no flow state exists)
    operations.flow_service.store.get_flow_state.return_value = None

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            label_state="",  # --label auto (no flow exists)
        )

        # Verify: BlockedStateService.unblock was called
        mock_service.unblock.assert_called_once()

        # Verify: target_state was READY (not CLAIMED)
        call_args = mock_service.unblock.call_args
        assert call_args.kwargs["target_state"] == IssueState.READY
        assert call_args.kwargs["issue_number"] == 303


def test_label_auto_with_missing_physical_worktree_requires_rebuild() -> None:
    """If label-auto resume finds a missing physical worktree, suggest rebuild."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.get_issue_body.return_value = "User content"
    operations.flow_service.store.get_flow_state.return_value = {
        "branch": "task/issue-303",
        "flow_slug": "issue-303",
        "flow_status": "blocked",
        "latest_actor": "test",
        "task_issue_number": 303,
        "worktree_path": "/tmp/missing-task-303",
    }
    operations.git_client.find_worktree_path_for_branch.return_value = None

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    # Task resume is manual operation - should raise UserError with rebuild suggestion
    with pytest.raises(UserError) as exc_info:
        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="missing worktree",
            label_state="",
        )

    assert "Worktree does not exist" in str(exc_info.value)
    assert "vibe3 flow rebuild 303 --yes" in str(exc_info.value)


def test_label_auto_with_unrecorded_existing_worktree_fixes_and_resumes() -> None:
    """A physical task worktree without flow_state.worktree_path gets backfilled."""
    operations = _make_operations()
    operations.github_client.get_issue_body.return_value = "User content"
    operations.flow_service.store.get_flow_state.return_value = {
        "branch": "task/issue-303",
        "flow_slug": "issue-303",
        "flow_status": "blocked",
        "latest_actor": "test",
        "task_issue_number": 303,
        "worktree_path": None,
    }
    operations.git_client.find_worktree_path_for_branch.return_value = (
        "/tmp/task-issue-303"
    )

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.flow.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="resume inconsistent scene",
            label_state="",
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: BlockedStateService.unblock was called (resume succeeded)
        mock_service.unblock.assert_called_once()

        # Verify: DB was backfilled with worktree_path
        operations.flow_service.store.update_flow_state.assert_called()
