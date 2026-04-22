"""Tests for task resume scene reset operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services.task_resume_operations import TaskResumeOperations


def _make_operations() -> TaskResumeOperations:
    git_client = MagicMock()
    github_client = MagicMock()
    flow_service = MagicMock()
    flow_service.store = MagicMock()
    label_service = MagicMock()
    issue_flow_service = MagicMock()
    issue_flow_service.is_task_branch.return_value = True
    return TaskResumeOperations(
        git_client=git_client,
        github_client=github_client,
        flow_service=flow_service,
        label_service=label_service,
        issue_flow_service=issue_flow_service,
    )


def test_reset_task_scene_deletes_branch_handoff_and_flow_truth() -> None:
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-329"
    )
    operations.git_client.branch_exists.return_value = True

    with patch(
        "vibe3.services.task_resume_operations.HandoffService"
    ) as mock_handoff_cls:
        handoff_service = MagicMock()
        mock_handoff_cls.return_value = handoff_service

        operations.reset_task_scene("task/issue-329")

    operations.git_client.remove_worktree.assert_called_once_with(
        "/tmp/issue-329", force=True
    )
    operations.git_client.delete_branch.assert_called_once_with(
        "task/issue-329",
        force=True,
        skip_if_worktree=True,
    )
    handoff_service.clear_handoff_for_branch.assert_called_once_with("task/issue-329")
    operations.flow_service.delete_flow.assert_called_once_with("task/issue-329")


def test_reset_issue_to_ready_without_label_deletes_worktree() -> None:
    """Without --label, should call reset_task_scene to delete worktree."""
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-303"
    )
    operations.git_client.branch_exists.return_value = True
    operations.label_service.get_state.return_value = IssueState.BLOCKED

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.task_resume_operations.HandoffService"
    ) as mock_handoff_cls:
        handoff_service = MagicMock()
        mock_handoff_cls.return_value = handoff_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            worktree_path="/tmp/issue-303",
            label_state=None,  # ← No --label
        )

    # Verify: worktree deleted (reset_task_scene called)
    operations.git_client.remove_worktree.assert_called_once()
    operations.git_client.delete_branch.assert_called_once()


def test_reset_issue_to_ready_with_label_keeps_worktree() -> None:
    """With --label (no value), should NOT call reset_task_scene (keep worktree)."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    operations.reset_issue_to_ready(
        issue_number=303,
        resume_kind="blocked",
        flow=mock_flow,
        repo=None,
        reason="test resume",
        worktree_path="/tmp/issue-303",
        label_state="handoff",  # ← --label (defaults to handoff)
    )

    # Verify: worktree NOT deleted (reset_task_scene NOT called)
    operations.git_client.remove_worktree.assert_not_called()
    operations.git_client.delete_branch.assert_not_called()

    # Verify: state restored to HANDOFF
    operations.label_service.confirm_issue_state.assert_called_once_with(
        303,
        IssueState.HANDOFF,
        actor="human:resume",
        force=True,
    )

    # Verify: reasons cleared (minimal cleanup, flow record preserved)
    operations.flow_service.store.update_flow_state.assert_called_once()


def test_reset_issue_to_ready_with_label_ready_restores_to_ready() -> None:
    """With --label ready, should restore to state/ready."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.FAILED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    operations.reset_issue_to_ready(
        issue_number=303,
        resume_kind="failed",
        flow=mock_flow,
        repo=None,
        reason="test resume",
        worktree_path="/tmp/issue-303",
        label_state="ready",  # ← --label ready
    )

    # Verify: worktree NOT deleted
    operations.git_client.remove_worktree.assert_not_called()

    # Verify: state restored to READY
    operations.label_service.confirm_issue_state.assert_called_once_with(
        303,
        IssueState.READY,
        actor="human:resume",
        force=True,
    )

    # Verify: reasons cleared (minimal cleanup, flow record preserved)
    operations.flow_service.store.update_flow_state.assert_called_once_with(
        "task/issue-303",
        blocked_reason=None,
        failed_reason=None,
        latest_actor="human:resume",
    )


def test_reset_issue_to_ready_with_label_handoff_explicit() -> None:
    """With --label handoff (explicit), should restore to state/handoff."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    operations.reset_issue_to_ready(
        issue_number=303,
        resume_kind="blocked",
        flow=mock_flow,
        repo=None,
        reason="test resume",
        worktree_path="/tmp/issue-303",
        label_state="handoff",  # ← --label handoff (explicit)
    )

    # Verify: worktree NOT deleted
    operations.git_client.remove_worktree.assert_not_called()

    # Verify: state restored to HANDOFF
    operations.label_service.confirm_issue_state.assert_called_once_with(
        303,
        IssueState.HANDOFF,
        actor="human:resume",
        force=True,
    )

    # Verify: reasons cleared
    operations.flow_service.store.update_flow_state.assert_called_once()


def test_reset_issue_to_ready_with_label_claimed() -> None:
    """With --label claimed, should restore to state/claimed."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    operations.reset_issue_to_ready(
        issue_number=303,
        resume_kind="blocked",
        flow=mock_flow,
        repo=None,
        reason="test resume",
        worktree_path="/tmp/issue-303",
        label_state="claimed",  # ← --label claimed
    )

    # Verify: worktree NOT deleted
    operations.git_client.remove_worktree.assert_not_called()

    # Verify: state restored to CLAIMED
    operations.label_service.confirm_issue_state.assert_called_once_with(
        303,
        IssueState.CLAIMED,
        actor="human:resume",
        force=True,
    )


def test_reset_issue_to_ready_with_label_in_progress() -> None:
    """With --label in-progress, should restore to state/in-progress."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.FAILED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    operations.reset_issue_to_ready(
        issue_number=303,
        resume_kind="failed",
        flow=mock_flow,
        repo=None,
        reason="test resume",
        worktree_path="/tmp/issue-303",
        label_state="in-progress",  # ← --label in-progress
    )

    # Verify: worktree NOT deleted
    operations.git_client.remove_worktree.assert_not_called()

    # Verify: state restored to IN_PROGRESS
    operations.label_service.confirm_issue_state.assert_called_once_with(
        303,
        IssueState.IN_PROGRESS,
        actor="human:resume",
        force=True,
    )


def test_reset_issue_to_ready_with_label_review() -> None:
    """With --label review, should restore to state/review."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    operations.reset_issue_to_ready(
        issue_number=303,
        resume_kind="blocked",
        flow=mock_flow,
        repo=None,
        reason="test resume",
        worktree_path="/tmp/issue-303",
        label_state="review",  # ← --label review
    )

    # Verify: worktree NOT deleted
    operations.git_client.remove_worktree.assert_not_called()

    # Verify: state restored to REVIEW
    operations.label_service.confirm_issue_state.assert_called_once_with(
        303,
        IssueState.REVIEW,
        actor="human:resume",
        force=True,
    )


def test_reset_issue_to_ready_with_label_merge_ready() -> None:
    """With --label merge-ready, should restore to state/merge-ready."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.FAILED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    operations.reset_issue_to_ready(
        issue_number=303,
        resume_kind="failed",
        flow=mock_flow,
        repo=None,
        reason="test resume",
        worktree_path="/tmp/issue-303",
        label_state="merge-ready",  # ← --label merge-ready
    )

    # Verify: worktree NOT deleted
    operations.git_client.remove_worktree.assert_not_called()

    # Verify: state restored to MERGE_READY
    operations.label_service.confirm_issue_state.assert_called_once_with(
        303,
        IssueState.MERGE_READY,
        actor="human:resume",
        force=True,
    )


def test_clear_flow_reasons_clears_both_reasons() -> None:
    """_clear_flow_reasons should clear both blocked_reason and failed_reason."""
    operations = _make_operations()

    operations._clear_flow_reasons("task/issue-303", "blocked")

    # Verify: both reasons cleared
    operations.flow_service.store.update_flow_state.assert_called_once_with(
        "task/issue-303",
        blocked_reason=None,
        failed_reason=None,
        latest_actor="human:resume",
    )


def test_add_label_resume_comment_skips_duplicate() -> None:
    """_add_label_resume_comment should skip if latest comment matches."""
    operations = _make_operations()

    # Setup: latest comment already matches (full content)
    expected_comment = (
        "[resume] 已从 state/blocked 恢复到 state/handoff。\n\n"
        "已清除 blocked_reason/failed_reason，保留 worktree现场。\n"
        "后续可在当前 worktree 继续推进。"
    )
    operations.github_client.view_issue.return_value = {
        "comments": [{"body": expected_comment}]
    }

    operations._add_label_resume_comment(
        issue_number=303,
        resume_kind="blocked",
        target_state=IssueState.HANDOFF,
        repo=None,
        reason="",
    )

    # Verify: comment NOT added (duplicate)
    operations.github_client.add_comment.assert_not_called()
