"""Tests for task resume scene reset operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

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
