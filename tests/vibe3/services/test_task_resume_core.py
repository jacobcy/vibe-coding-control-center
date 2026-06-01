"""Tests for core task resume operations."""

from unittest.mock import MagicMock, patch

import pytest

from tests.vibe3.services.conftest import _make_operations
from vibe3.exceptions import UserError
from vibe3.models.orchestration import IssueState


def test_reset_issue_to_ready_label_auto_keeps_worktree() -> None:
    """Label-auto resume clears blocked state without deleting the task scene."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED
    operations.flow_service.store.get_flow_state.return_value = {
        "branch": "task/issue-303",
        "flow_slug": "issue-303",
        "flow_status": "blocked",
        "latest_actor": "test",
        "task_issue_number": 303,
        "worktree_path": "/tmp/task-issue-303",
    }
    operations.git_client.find_worktree_path_for_branch.return_value = (
        "/tmp/task-issue-303"
    )

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-303"

    with patch(
        "vibe3.services.blocked_state_service.BlockedStateService"
    ) as mock_service_cls:
        mock_service = MagicMock()
        mock_service_cls.return_value = mock_service

        with patch(
            "vibe3.services.flow_cleanup_service.FlowCleanupService"
        ) as mock_cleanup_cls:
            operations.reset_issue_to_ready(
                issue_number=303,
                resume_kind="blocked",
                flow=mock_flow,
                repo=None,
                reason="test resume",
                label_state="",
            )

            mock_service.unblock.assert_called_once()
            mock_cleanup_cls.assert_not_called()


def test_reset_issue_to_ready_rejects_legacy_destructive_mode() -> None:
    """Task resume must not keep a legacy destructive reset path."""
    operations = _make_operations()
    operations.label_service.get_state.return_value = IssueState.BLOCKED

    mock_flow = MagicMock()
    mock_flow.branch = "task/issue-456"

    with patch("vibe3.services.flow_cleanup_service.FlowCleanupService") as cleanup_cls:
        with pytest.raises(UserError, match="FlowRebuildUsecase"):
            operations.reset_issue_to_ready(
                issue_number=456,
                resume_kind="blocked",
                flow=mock_flow,
                repo=None,
                reason="legacy destructive resume",
                label_state=None,
            )

        cleanup_cls.assert_not_called()


def test_task_resume_operations_does_not_expose_scene_reset_helper() -> None:
    """Destructive scene reset belongs to FlowRebuildUsecase, not task resume."""
    operations = _make_operations()

    assert not hasattr(operations, "reset_task_scene")
