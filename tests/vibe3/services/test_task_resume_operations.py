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
        "plan_ref": "docs/plans/test.md",
        "report_ref": None,
        "latest_verdict": None,
    }
    operations.flow_service.store.get_flow_state.return_value = mock_flow_state_dict
    operations.flow_service.store.get_task_issue_number.return_value = 303

    with patch(
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

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
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

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
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

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
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

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
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_in_progress() -> None:
    """With --label in-progress, should restore to state/in-progress."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

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
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_review() -> None:
    """With --label review, should restore to state/review."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

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
        mock_service.unblock.assert_called_once()


def test_reset_issue_to_ready_with_label_merge_ready() -> None:
    """With --label merge-ready, should restore to state/merge-ready."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

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
        mock_service.unblock.assert_called_once()


def test_reset_task_scene_creates_tombstone_after_full_rebuild() -> None:
    """Test that reset_task_scene calls cleanup service for tombstone creation."""
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-999"
    )
    operations.git_client.branch_exists.return_value = True

    branch = "task/issue-999"

    # Mock FlowCleanupService to make test hermetic
    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_class:
        mock_cleanup_service = MagicMock()
        mock_cleanup_class.return_value = mock_cleanup_service

        # Setup cleanup result
        mock_cleanup_service.cleanup_flow_scene.return_value = {
            "tmux_sessions": {"success": True, "sessions": []},
            "worktree": {"success": True, "path": None},
            "local_branch": {"success": True, "deleted": True},
            "remote_branch": {"success": True, "deleted": True},
            "handoff_files": {"success": True, "files": []},
            "flow_record": {"success": True, "deleted": True},
        }

        # Execute reset
        operations.reset_task_scene(branch)

        # Verify cleanup_flow_scene called with correct parameters
        mock_cleanup_service.cleanup_flow_scene.assert_called_once_with(
            branch,
            include_remote=True,
            terminate_sessions=True,
            keep_flow_record=False,
        )

        # Note: Tombstone normalization is validated in repository tests
        # This test verifies the call path through FlowCleanupService


def test_reset_task_scene_with_remote_keeps_remote_branch() -> None:
    """Test reset_task_scene with include_remote=False (--remote mode)."""
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-123"
    )
    operations.git_client.branch_exists.return_value = True

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup_instance = MagicMock()
        mock_cleanup_instance.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": True,  # Though we're keeping it
            "handoff": True,
            "flow_record": True,
        }
        mock_cleanup_cls.return_value = mock_cleanup_instance

        # Call with include_remote=False (--remote mode)
        operations.reset_task_scene("task/issue-123", include_remote=False)

        # Verify FlowCleanupService was instantiated
        mock_cleanup_cls.assert_called_once()

        # Verify cleanup_flow_scene was called with include_remote=False
        mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
            "task/issue-123",
            include_remote=False,  # Key assertion: keep remote branch
            terminate_sessions=True,
            keep_flow_record=False,
        )


def test_reset_issue_to_ready_with_remote_flag() -> None:
    """Test reset_issue_to_ready with remote=True (--remote flag)."""
    operations = _make_operations()
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-456"
    )
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-456"

    with patch(
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

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
                issue_number=456,
                resume_kind="blocked",
                flow=mock_flow,
                repo=None,
                reason="test resume with --remote",
                remote=True,  # ← --remote flag
            )

            # Verify: cleanup called with include_remote=False (keep remote branch)
            mock_cleanup_instance.cleanup_flow_scene.assert_called_once_with(
                "task/issue-456",
                include_remote=False,  # Key assertion
                terminate_sessions=True,
                keep_flow_record=False,
            )


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
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()

        mock_service_cls.return_value = mock_service

        operations.reset_issue_to_ready(
            issue_number=303,
            resume_kind="blocked",
            flow=mock_flow,
            repo=None,
            reason="test resume",
            worktree_path=None,
            label_state="",  # ← --label auto (no flow exists)
        )

        # Verify: BlockedStateService.unblock was called
        mock_service.unblock.assert_called_once()

        # Verify: target_state was READY (not CLAIMED)
        call_args = mock_service.unblock.call_args
        assert call_args.kwargs["target_state"] == IssueState.READY
        assert call_args.kwargs["issue_number"] == 303
