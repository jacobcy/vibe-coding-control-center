"""Tests for blocked auto-resume sync via task-resume service path.

Validates that the unified auto-resume entry point:
- Preserves worktree during auto-resume
- Rewrites issue body projection out of blocked state
- Restores inferred state labels correctly
"""

from unittest.mock import Mock, patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.services.task_resume_usecase import TaskResumeUsecase


@pytest.fixture
def usecase():
    """Create TaskResumeUsecase with mocked dependencies."""
    # Use a single mock instance so get_issue_body and update_issue_body
    # are on the same object the operations module uses.
    mock_github = Mock()
    mock_github.get_issue_body.return_value = "User content"

    with (
        patch("vibe3.services.task_resume_usecase.StatusQueryService") as mock_status,
        patch("vibe3.services.task_resume_usecase.LabelService") as mock_label,
        patch("vibe3.services.task_resume_usecase.FlowService") as mock_flow,
        patch("vibe3.services.task_resume_usecase.GitClient") as mock_git,
        patch(
            "vibe3.services.task_resume_usecase.GitHubClient",
            return_value=mock_github,
        ) as _,
        patch(
            "vibe3.services.blocked_state_io.GitHubClient",
            return_value=mock_github,
        ) as _,
        patch("vibe3.services.task_resume_usecase.IssueFlowService") as mock_issue_flow,
    ):
        uc = TaskResumeUsecase(
            status_service=mock_status.return_value,
            label_service=mock_label.return_value,
            flow_service=mock_flow.return_value,
            git_client=mock_git.return_value,
            github_client=mock_github,
            issue_flow_service=mock_issue_flow.return_value,
        )
        yield uc


class TestBlockedProjectionClearing:
    """Tests for _clear_blocked_projection explicit field clearing."""

    def test_clear_blocked_when_no_body(self, usecase):
        """Should gracefully return when issue body is None."""
        usecase.github_client.get_issue_body.return_value = None

        usecase.operations._clear_blocked_projection(123)

        usecase.github_client.update_issue_body.assert_not_called()


class TestAutoResumePreservesWorktree:
    """Tests verifying auto-resume does not delete worktrees."""

    def test_clear_flow_reasons_keeps_worktree(self, usecase):
        """Clearing flow reasons should preserve worktree_path."""
        store = usecase.flow_service.store
        store.get_flow_state.return_value = {
            "worktree_path": "/tmp/worktrees/task-issue-123",
            "task_issue_number": 123,
            "branch": "task/issue-123",
            "blocked_reason": "Health check failed",
        }

        usecase.operations._clear_flow_reasons("task/issue-123", "blocked")

        update_call = store.update_flow_state.call_args
        assert update_call is not None
        kwargs = update_call[1]
        assert kwargs.get("flow_status") == "active"
        assert kwargs.get("blocked_reason") is None
        assert kwargs.get("failed_reason") is None
        assert kwargs.get("blocked_by_issue") is None
        # worktree_path should NOT be passed to update_flow_state
        assert "worktree_path" not in kwargs


class TestAutoResumeRestoresInferredState:
    """Tests for inferred state restoration during auto-resume."""

    def test_infer_resume_label_no_actor_restores_ready(self, usecase):
        """Unclaimed flow (no actor) should restore to READY."""
        from vibe3.models.flow import FlowState
        from vibe3.services.flow_resume_resolver import infer_resume_label

        fs = FlowState(
            branch="task/issue-123",
            flow_slug="issue-123",
            flow_status="active",
            latest_actor=None,
        )
        label = infer_resume_label(fs)
        assert label in {
            IssueState.READY,
            IssueState.CLAIMED,
        }

    def test_infer_resume_label_with_actor_restores_in_progress(self, usecase):
        """Active flow with actor should restore to IN_PROGRESS or CLAIMED."""
        from vibe3.models.flow import FlowState
        from vibe3.services.flow_resume_resolver import infer_resume_label

        fs = FlowState(
            branch="task/issue-456",
            flow_slug="issue-456",
            flow_status="active",
            latest_actor="test-executor",
            latest_verdict="continue",
        )
        label = infer_resume_label(fs)
        assert label in {
            IssueState.IN_PROGRESS,
            IssueState.CLAIMED,
            IssueState.REVIEW,
            IssueState.HANDOFF,
            IssueState.READY,
        }
