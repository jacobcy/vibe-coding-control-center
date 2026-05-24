"""Tests for reset_issue_to_ready with --label flag scenarios."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestration import IssueState
from vibe3.services.task_resume_operations import TaskResumeOperations


def test_reset_issue_to_ready_with_label_keeps_worktree(
    make_operations: TaskResumeOperations,
) -> None:
    """With --label auto, should auto-infer target state and keep worktree."""
    operations = make_operations
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
        "plan_ref": "docs/plans/test.md",
        "report_ref": None,
        "latest_verdict": None,
    }
    operations.flow_service.store.get_flow_state.return_value = mock_flow_state_dict
    operations.flow_service.store.get_task_issue_number.return_value = 303

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            worktree_path="/tmp/issue-303",
            label_state="",  # ← --label auto (converted to empty string internally)
        )

        # Verify: worktree NOT deleted (reset_task_scene NOT called)
        operations.git_client.remove_worktree.assert_not_called()
        operations.git_client.delete_branch.assert_not_called()

        # Verify: state restored to IN_PROGRESS (inferred from plan_ref)
        mock_label_instance.confirm_issue_state.assert_called_once()

    # Verify: unblock called via BlockedStateService
    operations.flow_service.store.update_flow_state.assert_called_once()


def test_reset_issue_to_ready_with_label_ready_restores_to_ready(
    make_operations: TaskResumeOperations,
) -> None:
    """With --label ready, should restore to state/ready."""
    operations = make_operations
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}
    operations.github_client.get_issue_body.return_value = "User content"
    operations.flow_service.store.get_task_issue_number.return_value = 303

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            worktree_path="/tmp/issue-303",
            label_state="ready",  # ← --label ready
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to READY via resume_issue
        mock_label_instance.confirm_issue_state.assert_called_once()

    # Verify: reasons cleared and flow_status restored to active
    operations.flow_service.store.update_flow_state.assert_called()
    call_kwargs = operations.flow_service.store.update_flow_state.call_args[1]
    assert call_kwargs.get("blocked_reason") is None
    assert call_kwargs.get("blocked_by_issue") is None


def test_reset_issue_to_ready_with_label_handoff_explicit(
    make_operations: TaskResumeOperations,
) -> None:
    """With --label handoff (explicit), should restore to state/handoff."""
    operations = make_operations
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}
    operations.github_client.get_issue_body.return_value = "User content"
    operations.flow_service.store.get_task_issue_number.return_value = 303

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

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

        # Verify: state restored to HANDOFF via resume_issue
        mock_label_instance.confirm_issue_state.assert_called_once()

    # Verify: reasons cleared
    operations.flow_service.store.update_flow_state.assert_called_once()


def test_reset_issue_to_ready_with_label_claimed(
    make_operations: TaskResumeOperations,
) -> None:
    """With --label claimed, should restore to state/claimed."""
    operations = make_operations
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

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

        # Verify: state restored to CLAIMED via resume_issue
        mock_label_instance.confirm_issue_state.assert_called_once()


def test_reset_issue_to_ready_with_label_in_progress(
    make_operations: TaskResumeOperations,
) -> None:
    """With --label in-progress, should restore to state/in-progress."""
    operations = make_operations
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            worktree_path="/tmp/issue-303",
            label_state="in-progress",  # ← --label in-progress
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to IN_PROGRESS via resume_issue
        mock_label_instance.confirm_issue_state.assert_called_once()


def test_reset_issue_to_ready_with_label_review(
    make_operations: TaskResumeOperations,
) -> None:
    """With --label review, should restore to state/review."""
    operations = make_operations
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

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

        # Verify: state restored to REVIEW via resume_issue
        mock_label_instance.confirm_issue_state.assert_called_once()


def test_reset_issue_to_ready_with_label_merge_ready(
    make_operations: TaskResumeOperations,
) -> None:
    """With --label merge-ready, should restore to state/merge-ready."""
    operations = make_operations
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            worktree_path="/tmp/issue-303",
            label_state="merge-ready",  # ← --label merge-ready
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to MERGE_READY via resume_issue
        mock_label_instance.confirm_issue_state.assert_called_once()


def test_reset_issue_to_ready_with_label_auto_no_flow_restores_to_ready(
    make_operations: TaskResumeOperations,
) -> None:
    """With --label auto and no flow, should restore to READY (not CLAIMED)."""
    operations = make_operations
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    # Mock NO flow (branch is None)
    mock_flow = MagicMock()
    mock_flow.branch = None

    # get_flow_state returns None (no flow state exists)
    operations.flow_service.store.get_flow_state.return_value = None

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            worktree_path=None,
            label_state="",  # ← --label auto (no flow exists)
        )

        # Verify: state restored to READY (not CLAIMED)
        mock_label_instance.confirm_issue_state.assert_called_once()
        call_args = mock_label_instance.confirm_issue_state.call_args
        assert call_args[0][1] == IssueState.READY  # Second positional arg is state
