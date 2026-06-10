"""Tests for enhanced block_flow() behavior.

Covers:
- Issue state transition to BLOCKED when blocking flow with issue number
- Comment addition to issue when blocking with reason
- block_flow works without task_issue_number (graceful degradation)
- block_flow transitions label but doesn't add comment when reason is None
"""

from unittest.mock import MagicMock, patch

import pytest

from vibe3.models.orchestration import IssueState
from vibe3.services.flow.service import FlowService


@pytest.fixture
def mock_store():
    """Mock SQLiteClient store."""
    store = MagicMock()
    # Mock existing flow state
    store.get_flow_state.return_value = {
        "branch": "task/issue-42",
        "flow_slug": "issue-42",
        "task_issue_number": 42,
        "latest_actor": "test-actor",
    }
    # Mock get_task_issue_number for unified resolution
    store.get_task_issue_number.return_value = None  # Default: fallback to issue_links
    return store


@pytest.fixture
def mock_label_service():
    """Mock LabelService."""
    with patch("vibe3.services.flow.blocked_state_io.LabelService") as mock:
        yield mock.return_value


@pytest.fixture
def mock_flow_timeline_service():
    """Mock FlowTimelineService."""
    with patch("vibe3.services.blocked_state_service.FlowTimelineService") as mock:
        yield mock.return_value


@pytest.fixture
def mock_github_client():
    """Mock GitHubClient."""
    with patch("vibe3.services.flow.blocked_state_io.GitHubClient") as mock:
        mock_instance = mock.return_value
        mock_instance.get_issue_body.return_value = "Test issue body"
        yield mock_instance


@pytest.fixture
def service(mock_store, mock_label_service, mock_flow_timeline_service):
    """Create FlowService instance with mocked dependencies."""
    service = FlowService(store=mock_store)
    service.label_service = mock_label_service
    service.flow_timeline_service = mock_flow_timeline_service
    return service


class TestBlockFlowEnhanced:
    """Enhanced block_flow() behavior tests."""

    def test_block_flow_transitions_issue_state(
        self,
        service: FlowService,
        mock_store,
        mock_label_service,
        mock_flow_timeline_service,
        mock_github_client,
    ):
        """block_flow transitions issue state to BLOCKED and adds comment."""
        # Arrange
        branch = "task/issue-42"
        reason = "Waiting for dependency"
        actor = "test-actor"

        # Mock get_issue_links to return task issue link
        mock_store.get_issue_links.return_value = [
            {"issue_number": 42, "issue_role": "task"}
        ]

        # Act
        service.block_flow(branch=branch, reason=reason, actor=actor)

        # Assert - Issue state transition (via confirm_issue_state)
        mock_label_service.confirm_issue_state.assert_called_once_with(
            42, IssueState.BLOCKED, actor=actor, force=False
        )

        # Assert - Timeline comment added
        mock_flow_timeline_service.record_timeline_event.assert_called_once_with(
            branch=branch,
            event_type="flow_blocked",
            actor=actor,
            detail=reason,
            issue_number=42,
        )

        # Assert - Flow state updated (existing behavior)
        mock_store.update_flow_state.assert_called_once()
        update_kwargs = mock_store.update_flow_state.call_args[1]
        assert update_kwargs["blocked_reason"] == reason
        assert update_kwargs["latest_actor"] == actor

    def test_block_flow_without_issue_number(
        self,
        service: FlowService,
        mock_store,
        mock_label_service,
        mock_flow_timeline_service,
    ):
        """block_flow works without task_issue_number (graceful degradation)."""
        # Arrange - flow without issue number
        branch = "feature/some-branch"
        reason = "Waiting for dependency"
        actor = "test-actor"

        mock_store.get_flow_state.return_value = {
            "branch": branch,
            "flow_slug": "some-flow",
            "latest_actor": actor,
            # No task_issue_number
        }

        # Act
        service.block_flow(branch=branch, reason=reason, actor=actor)

        # Assert - No issue state transition (no issue number)
        mock_label_service.confirm_issue_state.assert_not_called()

        # Assert - No timeline comment added (no issue number)
        mock_flow_timeline_service.record_timeline_event.assert_not_called()

        # Assert - Flow state still updated
        mock_store.update_flow_state.assert_called_once()
        update_kwargs = mock_store.update_flow_state.call_args[1]
        assert update_kwargs["blocked_reason"] == reason
        assert update_kwargs["latest_actor"] == actor

    def test_block_flow_without_reason(
        self,
        service: FlowService,
        mock_store,
        mock_label_service,
        mock_flow_timeline_service,
        mock_github_client,
    ):
        """block_flow transitions label but doesn't add comment when reason is None."""
        # Arrange
        branch = "task/issue-42"
        reason = None
        actor = "test-actor"

        # Mock get_issue_links to return task issue link
        mock_store.get_issue_links.return_value = [
            {"issue_number": 42, "issue_role": "task"}
        ]

        # Act
        service.block_flow(branch=branch, reason=reason, actor=actor)

        # Assert - Issue state transition still happens (via confirm_issue_state)
        mock_label_service.confirm_issue_state.assert_called_once_with(
            42, IssueState.BLOCKED, actor=actor, force=False
        )

        # Assert - Timeline comment added with empty reason
        # (reason becomes "" in block() for timeline detail)
        mock_flow_timeline_service.record_timeline_event.assert_called_once_with(
            branch=branch,
            event_type="flow_blocked",
            actor=actor,
            detail="",  # reason is None becomes "" for timeline
            issue_number=42,
        )

        # Assert - Flow state updated with None reason (preserved)
        mock_store.update_flow_state.assert_called_once()
        update_kwargs = mock_store.update_flow_state.call_args[1]
        assert update_kwargs["blocked_reason"] is None
        assert update_kwargs["latest_actor"] == actor
