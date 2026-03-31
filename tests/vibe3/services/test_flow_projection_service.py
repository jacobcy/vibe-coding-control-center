"""Tests for Flow projection service."""

from unittest.mock import MagicMock

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.pr import PRResponse, PRState
from vibe3.services.flow_projection_service import FlowProjectionService


def test_flow_projection_basic():
    """Test basic projection creation from local flow state."""
    mock_flow_service = MagicMock()
    mock_flow_status = FlowStatusResponse(
        branch="task/test-branch",
        flow_slug="test-branch",
        flow_status="active",
        task_issue_number=123,
        pr_number=456,
        spec_ref="docs/spec.md",
        next_step="Implement feature",
    )
    mock_flow_service.get_flow_status.return_value = mock_flow_status

    mock_task_service = MagicMock()
    mock_pr_service = MagicMock()

    service = FlowProjectionService(
        flow_service=mock_flow_service,
        task_service=mock_task_service,
        pr_service=mock_pr_service,
    )

    projection = service.get_projection("task/test-branch", include_remote=False)

    assert projection.branch == "task/test-branch"
    assert projection.flow_slug == "test-branch"
    assert projection.flow_status == "active"
    assert projection.task_issue_number == 123
    assert projection.pr_number == 456
    assert projection.spec_ref == "docs/spec.md"
    assert projection.next_step == "Implement feature"
    assert projection.offline_mode is False
    assert projection.hydrate_error is None
    assert projection.pr_fetch_error is None


def test_flow_projection_with_remote_pr_data():
    """Test projection with remote PR data."""
    mock_flow_service = MagicMock()
    mock_flow_status = FlowStatusResponse(
        branch="task/test-branch",
        flow_slug="test-branch",
        flow_status="active",
        task_issue_number=123,
    )
    mock_flow_service.get_flow_status.return_value = mock_flow_status

    # Mock PR fetch
    mock_pr = PRResponse(
        number=456,
        title="Test PR Title",
        state=PRState.OPEN,
        draft=False,
        url="https://github.com/test/repo/pull/456",
        head_branch="task/test-branch",
        base_branch="main",
        body="PR body",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    mock_pr_service = MagicMock()
    mock_pr_service.github_client.list_prs_for_branch.return_value = [mock_pr]

    service = FlowProjectionService(
        flow_service=mock_flow_service,
        pr_service=mock_pr_service,
    )

    projection = service.get_projection("task/test-branch")

    assert projection.pr_number == 456
    assert projection.pr_status == "OPEN"
    assert projection.pr_is_draft is False
    assert projection.pr_url == "https://github.com/test/repo/pull/456"
