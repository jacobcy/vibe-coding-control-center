"""Tests for task resume operations with body projection."""

from unittest.mock import patch

from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_flow_service import IssueFlowService
from vibe3.services.label_service import LabelService
from vibe3.services.task_resume_operations import TaskResumeOperations


def test_clear_flow_reasons_clears_blocked_projection() -> None:
    """Test that _clear_flow_reasons clears blocked state from issue body."""
    git_client = GitClient()
    github_client = GitHubClient()
    flow_service = FlowService()
    label_service = LabelService()
    issue_flow_service = IssueFlowService()

    operations = TaskResumeOperations(
        git_client=git_client,
        github_client=github_client,
        flow_service=flow_service,
        label_service=label_service,
        issue_flow_service=issue_flow_service,
    )

    with (
        patch.object(flow_service.store, "update_flow_state"),
        patch.object(flow_service.store, "get_flow_state") as mock_get,
        patch.object(operations, "_clear_blocked_projection") as mock_clear,
    ):
        # Setup flow state with issue number
        mock_get.return_value = {
            "branch": "task/issue-123",
            "task_issue_number": 123,
            "blocked_reason": "API design pending",
        }

        # Execute
        operations._clear_flow_reasons("task/issue-123", "blocked")

        # Verify _clear_blocked_projection called with issue number
        mock_clear.assert_called_once_with(123)


def test_clear_blocked_projection_updates_issue_body() -> None:
    """Test that _clear_blocked_projection correctly clears managed section."""
    git_client = GitClient()
    github_client = GitHubClient()
    flow_service = FlowService()
    label_service = LabelService()
    issue_flow_service = IssueFlowService()

    operations = TaskResumeOperations(
        git_client=git_client,
        github_client=github_client,
        flow_service=flow_service,
        label_service=label_service,
        issue_flow_service=issue_flow_service,
    )

    # Mock issue body with blocked state
    blocked_body = """User content here.

<!-- vibe3-flow-state-start -->

**Vibe3 Flow State**

- **State**: blocked
- **Blocked by**: #456
- **Blocked reason**: API design pending

<!-- vibe3-flow-state-end -->"""

    with patch.object(github_client, "get_issue_body") as mock_get:
        mock_get.return_value = blocked_body

        with patch.object(github_client, "update_issue_body") as mock_update:
            mock_update.return_value = True

            # Execute
            operations._clear_blocked_projection(123)

            # Verify get_issue_body called
            mock_get.assert_called_once_with(123)

            # Verify update_issue_body called
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == 123  # issue_number
            merged_body = call_args[0][1]

            # Verify managed section is cleared (empty projection)
            assert "User content here" in merged_body
            assert "**Vibe3 Flow State**" not in merged_body
            assert "- **State**: blocked" not in merged_body


def test_clear_blocked_projection_handles_none_body() -> None:
    """Test that _clear_blocked_projection handles missing issue body."""
    git_client = GitClient()
    github_client = GitHubClient()
    flow_service = FlowService()
    label_service = LabelService()
    issue_flow_service = IssueFlowService()

    operations = TaskResumeOperations(
        git_client=git_client,
        github_client=github_client,
        flow_service=flow_service,
        label_service=label_service,
        issue_flow_service=issue_flow_service,
    )

    with patch.object(github_client, "get_issue_body") as mock_get:
        mock_get.return_value = None

        with patch.object(github_client, "update_issue_body") as mock_update:
            # Execute
            operations._clear_blocked_projection(123)

            # Verify update_issue_body not called when body is None
            mock_update.assert_not_called()


def test_reset_task_scene_creates_tombstone_after_full_rebuild() -> None:
    """Test that reset_task_scene normalizes deleted flow to tombstone."""

    git_client = GitClient()
    github_client = GitHubClient()
    flow_service = FlowService()
    label_service = LabelService()
    issue_flow_service = IssueFlowService()

    operations = TaskResumeOperations(
        git_client=git_client,
        github_client=github_client,
        flow_service=flow_service,
        label_service=label_service,
        issue_flow_service=issue_flow_service,
    )

    branch = "task/issue-999"

    with (
        patch.object(git_client, "find_worktree_path_for_branch", return_value=None),
        patch.object(git_client, "branch_exists", return_value=False),
        patch.object(git_client, "delete_branch"),
        patch.object(flow_service.store, "update_flow_state"),
        patch.object(flow_service.store, "get_flow_state") as mock_get,
        patch.object(flow_service.store, "soft_delete_flow") as mock_delete,
    ):
        # Setup: flow with active metadata before reset
        mock_get.return_value = {
            "branch": branch,
            "flow_slug": "issue_999",
            "flow_status": "active",
            "plan_ref": "docs/plans/test.md",
            "report_ref": "docs/reports/test.md",
            "worktree_path": "/tmp/worktree",
            "blocked_reason": "Test block",
        }

        # Execute full rebuild reset
        operations.reset_task_scene(branch)

        # Verify soft_delete_flow called (creates tombstone)
        mock_delete.assert_called_once_with(branch)

        # Note: The actual tombstone validation is in repository tests
        # This test verifies the call path from task resume to soft_delete
