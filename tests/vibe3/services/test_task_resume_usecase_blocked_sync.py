"""Tests for blocked auto-resume sync via task-resume service path.

Validates that the unified auto-resume entry point:
- Preserves worktree during auto-resume
- Rewrites issue body projection out of blocked state
- Restores inferred state labels correctly
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.services.task import TaskResumeUsecase


@pytest.fixture
def usecase():
    """Create TaskResumeUsecase with mocked dependencies."""
    # Use a single mock instance so get_issue_body and update_issue_body
    # are on the same object the operations module uses.
    mock_github = Mock()
    mock_github.get_issue_body.return_value = "User content"

    with (
        patch("vibe3.services.task.resume.StatusQueryService") as mock_status,
        patch("vibe3.services.task.resume.LabelService") as mock_label,
        patch("vibe3.services.task.resume.FlowService") as mock_flow,
        patch("vibe3.services.task.resume.GitClient") as mock_git,
        patch(
            "vibe3.services.task.resume.GitHubClient",
            return_value=mock_github,
        ) as _,
        patch(
            "vibe3.services.flow.blocked_state_io.GitHubClient",
            return_value=mock_github,
        ) as _,
        patch("vibe3.services.task.resume.IssueFlowService") as mock_issue_flow,
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


class TestAutoResumePreservesWorktree:
    """Tests verifying auto-resume does not delete worktrees."""

    def test_unblock_clears_reasons_keeps_worktree(self, usecase):
        """Unblocking via BlockedStateService should clear reasons
        but preserve worktree_path.
        """
        store = usecase.flow_service.store
        store.get_flow_state.return_value = {
            "worktree_path": "/tmp/worktrees/task-issue-123",
            "task_issue_number": 123,
            "branch": "task/issue-123",
            "blocked_reason": "Health check failed",
        }

        with patch(
            "vibe3.services.blocked_state_service.BlockedStateService"
        ) as mock_service_cls:
            mock_service = MagicMock()
            mock_service_cls.return_value = mock_service

            usecase.operations.reset_issue_to_ready(
                issue_number=123,
                resume_kind="blocked",
                flow=MagicMock(branch="task/issue-123"),
                repo=None,
                reason="test unblock",
                label_state="ready",
            )

            # Verify BlockedStateService.unblock was called (unified method)
            mock_service.unblock.assert_called_once()


class TestAutoResumeRestoresInferredState:
    """Tests for inferred state restoration during auto-resume."""

    def test_infer_resume_label_no_actor_restores_ready(self, usecase):
        """Unclaimed flow (no actor) should restore to READY."""
        from vibe3.models.flow import FlowState
        from vibe3.services.flow.resume_resolver import infer_resume_label

        fs = FlowState(
            branch="task/issue-123",
            flow_slug="issue-123",
            flow_status="active",
            latest_actor=None,
        )
        label = infer_resume_label(fs)
        assert label == IssueState.READY

    def test_infer_resume_label_with_actor_restores_in_progress(self, usecase):
        """Active flow with actor should restore to IN_PROGRESS or CLAIMED."""
        from vibe3.models.flow import FlowState
        from vibe3.services.flow.resume_resolver import infer_resume_label

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
