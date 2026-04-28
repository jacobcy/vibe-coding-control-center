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


def _mock_label_service():
    """Create a mock LabelService for resume_issue tests."""
    mock_label = MagicMock()
    mock_label.confirm_issue_state = MagicMock()
    mock_label.get_state = MagicMock(return_value=IssueState.READY)
    return mock_label


def test_reset_task_scene_deletes_branch_handoff_and_flow_truth() -> None:
    """Test that reset_task_scene uses FlowCleanupService for complete cleanup."""
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-329"
    )
    operations.git_client.branch_exists.return_value = True

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        operations.reset_task_scene("task/issue-329")

        # Verify FlowCleanupService was instantiated
        mock_cleanup_cls.assert_called_once()

        # Verify cleanup_flow_scene was called with correct parameters
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-329",
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,  # Resume always deletes flow record
        )


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
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            worktree_path="/tmp/issue-303",
            label_state=None,  # ← No --label
        )

        # Verify: cleanup_flow_scene was called (via reset_task_scene)
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once()


def test_reset_issue_to_ready_with_label_keeps_worktree() -> None:
    """With --label (no value), should NOT call reset_task_scene (keep worktree)."""
    operations = _make_operations()
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
            label_state="handoff",  # ← --label (defaults to handoff)
        )

        # Verify: worktree NOT deleted (reset_task_scene NOT called)
        operations.git_client.remove_worktree.assert_not_called()
        operations.git_client.delete_branch.assert_not_called()

        # Verify: state restored to HANDOFF via resume_issue
        mock_label_instance.confirm_issue_state.assert_called_once()

    # Verify: reasons cleared (minimal cleanup, flow record preserved)
    operations.flow_service.store.update_flow_state.assert_called_once()


def test_reset_issue_to_ready_with_label_ready_restores_to_ready() -> None:
    """With --label ready, should restore to state/ready."""
    operations = _make_operations()
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
            label_state="ready",  # ← --label ready
        )

        # Verify: worktree NOT deleted
        operations.git_client.remove_worktree.assert_not_called()

        # Verify: state restored to READY via resume_issue
        mock_label_instance.confirm_issue_state.assert_called_once()

    # Verify: reasons cleared (blocked_reason + failed_reason for backward compat)
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


def test_reset_issue_to_ready_with_label_claimed() -> None:
    """With --label claimed, should restore to state/claimed."""
    operations = _make_operations()
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


def test_reset_issue_to_ready_with_label_in_progress() -> None:
    """With --label in-progress, should restore to state/in-progress."""
    operations = _make_operations()
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


def test_reset_issue_to_ready_with_label_review() -> None:
    """With --label review, should restore to state/review."""
    operations = _make_operations()
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


def test_reset_issue_to_ready_with_label_merge_ready() -> None:
    """With --label merge-ready, should restore to state/merge-ready."""
    operations = _make_operations()
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


def test_clear_flow_reasons_clears_both_reasons() -> None:
    """_clear_flow_reasons should clear both blocked_reason and failed_reason."""
    operations = _make_operations()

    operations._clear_flow_reasons("task/issue-303", "blocked")

    # Verify: both reasons cleared (failed_reason for backward compat)
    operations.flow_service.store.update_flow_state.assert_called_once_with(
        "task/issue-303",
        blocked_reason=None,
        failed_reason=None,
        latest_actor="human:resume",
    )
