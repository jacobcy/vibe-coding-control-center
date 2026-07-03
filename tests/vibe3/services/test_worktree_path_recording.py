"""Test worktree_path recording for auto task branches."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.environment.worktree_lifecycle import WorktreeLifecycle


@pytest.fixture
def mock_config():
    """Mock OrchestraConfig."""
    config = MagicMock()
    config.repo = "jacobcy/vibe-coding-control-center"
    return config


@pytest.fixture
def mock_repo_path():
    """Mock repository path."""
    return Path("/tmp/test-repo")


@pytest.fixture
def lifecycle(mock_config, mock_repo_path):
    """Create WorktreeLifecycle instance with mock FlowService."""
    mock_flow_service = MagicMock()
    return WorktreeLifecycle(
        mock_config, mock_repo_path, flow_service=mock_flow_service
    )


class TestStep3RecordWorktreePath:
    """Test Step 3: existing worktree path recording."""

    def test_records_for_task_branch(self, lifecycle, mock_repo_path, mock_config):
        """Step 3 should record worktree_path for task/issue-* branches."""
        issue_number = 123
        flow_branch = "task/issue-123"
        existing_path = Path("/tmp/worktrees/task/issue-123")

        with (
            patch.object(
                lifecycle,
                "_try_recorded_path",
                return_value=None,
            ),
            patch(
                "vibe3.environment.worktree_support.find_worktree_for_branch",
                return_value=existing_path,
            ),
            patch.object(
                lifecycle,
                "validate_worktree_branch_for_issue",
                return_value=True,
            ),
            patch.object(
                lifecycle,
                "record_worktree_path",
            ) as mock_record,
        ):
            result = lifecycle.find_or_create_worktree_for_branch(
                issue_number=issue_number,
                flow_branch=flow_branch,
                repo_path=mock_repo_path,
                acquire_issue_worktree_func=MagicMock(),
            )

            # Verify worktree_path was recorded
            mock_record.assert_called_once_with(flow_branch, str(existing_path))
            assert result.path == existing_path
            assert result.branch == flow_branch
            assert result.issue_number == issue_number

    def test_skips_recording_for_dev_branch(
        self, lifecycle, mock_repo_path, mock_config
    ):
        """Step 3 should NOT record worktree_path for dev/issue-* branches."""
        issue_number = 456
        flow_branch = "dev/issue-456"
        existing_path = Path("/tmp/worktrees/dev/issue-456")

        with (
            patch.object(
                lifecycle,
                "_try_recorded_path",
                return_value=None,
            ),
            patch(
                "vibe3.environment.worktree_support.find_worktree_for_branch",
                return_value=existing_path,
            ),
            patch.object(
                lifecycle,
                "validate_worktree_branch_for_issue",
                return_value=True,
            ),
            patch.object(
                lifecycle,
                "record_worktree_path",
            ) as mock_record,
        ):
            result = lifecycle.find_or_create_worktree_for_branch(
                issue_number=issue_number,
                flow_branch=flow_branch,
                repo_path=mock_repo_path,
                acquire_issue_worktree_func=MagicMock(),
            )

            # Verify worktree_path was NOT recorded
            mock_record.assert_not_called()
            assert result.path == existing_path
            assert result.branch == flow_branch
            assert result.issue_number == issue_number


class TestStep4RecordWorktreePath:
    """Test Step 4: new worktree creation path recording."""

    def test_records_for_task_branch(self, lifecycle, mock_repo_path, mock_config):
        """Step 4 should record worktree_path for task/issue-* branches."""
        issue_number = 789
        flow_branch = "task/issue-789"
        new_path = Path("/tmp/worktrees/task/issue-789")
        mock_worktree_context = MagicMock()
        mock_worktree_context.path = new_path
        mock_worktree_context.branch = flow_branch
        mock_worktree_context.issue_number = issue_number

        with (
            patch.object(
                lifecycle,
                "_try_recorded_path",
                return_value=None,
            ),
            patch(
                "vibe3.environment.worktree_support.find_worktree_for_branch",
                return_value=None,
            ),
            patch.object(
                lifecycle,
                "record_worktree_path",
            ) as mock_record,
        ):
            mock_acquire = MagicMock(return_value=mock_worktree_context)

            result = lifecycle.find_or_create_worktree_for_branch(
                issue_number=issue_number,
                flow_branch=flow_branch,
                repo_path=mock_repo_path,
                acquire_issue_worktree_func=mock_acquire,
            )

            # Verify worktree_path was recorded
            mock_record.assert_called_once_with(flow_branch, str(new_path))
            assert result.path == new_path
            assert result.branch == flow_branch
            assert result.issue_number == issue_number

    def test_skips_recording_for_dev_branch(
        self, lifecycle, mock_repo_path, mock_config
    ):
        """Step 4 should NOT record worktree_path for dev/issue-* branches."""
        issue_number = 999
        flow_branch = "dev/issue-999"
        new_path = Path("/tmp/worktrees/dev/issue-999")
        mock_worktree_context = MagicMock()
        mock_worktree_context.path = new_path
        mock_worktree_context.branch = flow_branch
        mock_worktree_context.issue_number = issue_number

        with (
            patch.object(
                lifecycle,
                "_try_recorded_path",
                return_value=None,
            ),
            patch(
                "vibe3.environment.worktree_support.find_worktree_for_branch",
                return_value=None,
            ),
            patch.object(
                lifecycle,
                "record_worktree_path",
            ) as mock_record,
        ):
            mock_acquire = MagicMock(return_value=mock_worktree_context)

            result = lifecycle.find_or_create_worktree_for_branch(
                issue_number=issue_number,
                flow_branch=flow_branch,
                repo_path=mock_repo_path,
                acquire_issue_worktree_func=mock_acquire,
            )

            # Verify worktree_path was NOT recorded
            mock_record.assert_not_called()
            assert result.path == new_path
            assert result.branch == flow_branch
            assert result.issue_number == issue_number
