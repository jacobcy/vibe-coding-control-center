"""Tests for reset_issue_to_ready core operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState
from vibe3.services.task_resume_operations import TaskResumeOperations


def test_reset_issue_to_ready_without_label_deletes_worktree(
    make_operations: TaskResumeOperations,
) -> None:
    """Without --label, should call reset_task_scene to delete worktree."""
    operations = make_operations
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


def test_reset_issue_to_ready_blocks_when_branch_has_live_runtime_session(
    make_operations: TaskResumeOperations,
) -> None:
    """reset_issue_to_ready should block when branch has live runtime session."""
    operations = make_operations
    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"
    operations.label_service.get_state.return_value = IssueState.BLOCKED

    with (
        patch(
            "vibe3.environment.session_registry.SessionRegistryService"
        ) as mock_registry_cls,
        patch("vibe3.agents.backends.codeagent.CodeagentBackend"),
    ):
        mock_registry_instance = MagicMock()
        mock_registry_instance.get_truly_live_sessions_for_branch.return_value = [
            {"id": 1}
        ]
        mock_registry_cls.return_value = mock_registry_instance

        with pytest.raises(UserError, match="live runtime session"):
            operations.reset_issue_to_ready(
                issue_number=303,
                resume_kind="blocked",
                flow=mock_flow,
                repo=None,
                reason="test",
            )


def test_reset_issue_to_ready_with_remote_flag(
    make_operations: TaskResumeOperations,
) -> None:
    """Test reset_issue_to_ready with remote=True (--remote flag)."""
    operations = make_operations
    operations.git_client.find_worktree_path_for_branch.return_value = Path(
        "/tmp/issue-456"
    )
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.github_client.view_issue.return_value = {"comments": []}

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-456"

    with patch("vibe3.services.issue_failure_service.LabelService") as mock_label_cls:
        mock_label_instance = MagicMock()
        mock_label_instance.confirm_issue_state = MagicMock()
        mock_label_cls.return_value = mock_label_instance

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
