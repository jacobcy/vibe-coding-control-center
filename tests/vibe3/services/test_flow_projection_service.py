"""Tests for FlowProjectionService."""

from unittest.mock import MagicMock

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.pr import PRResponse, PRState
from vibe3.models.task_bridge import FieldSource, HydratedTaskView
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
        pr_ready_for_review=True,
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
    assert projection.pr_fetch_error is False


def test_flow_projection_with_remote_data():
    """Test projection with remote task and PR data."""
    mock_flow_service = MagicMock()
    mock_flow_status = FlowStatusResponse(
        branch="task/test-branch",
        flow_slug="test-branch",
        flow_status="active",
        task_issue_number=123,
    )
    mock_flow_service.get_flow_status.return_value = mock_flow_status

    # Mock task hydrate
    mock_task_view = HydratedTaskView(branch="task/test-branch")
    mock_task_view.title = FieldSource(value="Test Task Title", source="remote")
    mock_task_view.body = FieldSource(value="Test task body content", source="remote")
    mock_task_view.status = FieldSource(value="In Progress", source="remote")
    mock_task_view.assignees = FieldSource(value=["user1", "user2"], source="remote")
    mock_task_service = MagicMock()
    mock_task_service.hydrate.return_value = mock_task_view

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
    mock_pr_service.get_pr.return_value = mock_pr

    service = FlowProjectionService(
        flow_service=mock_flow_service,
        task_service=mock_task_service,
        pr_service=mock_pr_service,
    )

    projection = service.get_projection("task/test-branch")

    assert projection.title == "Test Task Title"
    assert projection.body == "Test task body content"
    assert projection.status == "In Progress"
    assert projection.assignees == ["user1", "user2"]
    assert projection.pr_number == 456
    assert projection.pr_title == "Test PR Title"
    assert projection.pr_state == "OPEN"
    assert projection.pr_draft is False
    assert projection.pr_ready_for_review is True
    assert projection.pr_url == "https://github.com/test/repo/pull/456"


def test_flow_projection_offline_mode():
    """Test projection when remote fetch fails."""
    mock_flow_service = MagicMock()
    mock_flow_status = FlowStatusResponse(
        branch="task/test-branch",
        flow_slug="test-branch",
        flow_status="active",
        task_issue_number=123,
    )
    mock_flow_service.get_flow_status.return_value = mock_flow_status

    # Mock task hydrate to return offline view
    mock_task_view = HydratedTaskView(branch="task/test-branch")
    mock_task_view.offline_mode = True
    mock_task_service = MagicMock()
    mock_task_service.hydrate.return_value = mock_task_view

    # Mock PR fetch to fail
    mock_pr_service = MagicMock()
    mock_pr_service.get_pr.side_effect = Exception("Network error")

    service = FlowProjectionService(
        flow_service=mock_flow_service,
        task_service=mock_task_service,
        pr_service=mock_pr_service,
    )

    projection = service.get_projection("task/test-branch")

    assert projection.offline_mode is True
    assert projection.pr_fetch_error is True
    assert projection.title is None
    assert projection.pr_number is None


def test_get_issue_titles():
    """Test fetching issue titles from GitHub."""
    mock_github_client = MagicMock()
    mock_github_client.view_issue.side_effect = [
        {"title": "Issue 123"},
        {"title": "Issue 456"},
    ]

    service = FlowProjectionService(github_client=mock_github_client)
    titles, network_error = service.get_issue_titles([123, 456])

    assert network_error is False
    assert titles == {123: "Issue 123", 456: "Issue 456"}
    assert mock_github_client.view_issue.call_count == 2


def test_get_issue_titles_network_error():
    """Test issue title fetch with network error."""
    mock_github_client = MagicMock()
    mock_github_client.view_issue.side_effect = [
        {"title": "Issue 123"},
        "network_error",
    ]

    service = FlowProjectionService(github_client=mock_github_client)
    titles, network_error = service.get_issue_titles([123, 456])

    assert network_error is True
    assert titles == {123: "Issue 123"}


def test_get_milestone_data():
    """Test fetching milestone data."""
    mock_github_client = MagicMock()
    mock_github_client.view_issue.return_value = {
        "milestone": {
            "number": 10,
            "title": "Milestone 1.0",
        }
    }
    mock_github_client.get_milestone_issues.return_value = [
        {"state": "OPEN"},
        {"state": "CLOSED"},
        {"state": "OPEN"},
    ]

    service = FlowProjectionService(github_client=mock_github_client)
    milestone_data = service.get_milestone_data(123)

    assert milestone_data is not None
    assert milestone_data["number"] == 10
    assert milestone_data["title"] == "Milestone 1.0"
    assert milestone_data["open"] == 2
    assert milestone_data["closed"] == 1
    assert milestone_data["task_issue"] == 123
