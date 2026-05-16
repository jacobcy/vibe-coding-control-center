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
from vibe3.services.flow_service import FlowService


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
    return store


@pytest.fixture
def mock_label_service():
    """Mock LabelService."""
    with patch("vibe3.services.flow_block_mixin.LabelService") as mock:
        yield mock.return_value


@pytest.fixture
def mock_github_client():
    """Mock GitHubClient."""
    with patch("vibe3.services.flow_block_mixin.GitHubClient") as mock:
        yield mock.return_value


@pytest.fixture
def service(mock_store, mock_label_service, mock_github_client):
    """Create FlowService instance with mocked dependencies."""
    service = FlowService(store=mock_store)
    service.label_service = mock_label_service
    service.github_client = mock_github_client
    return service


class TestBlockFlowEnhanced:
    """Enhanced block_flow() behavior tests."""

    def test_block_flow_transitions_issue_state(
        self, service: FlowService, mock_store, mock_label_service, mock_github_client
    ):
        """block_flow transitions issue state to BLOCKED and adds comment."""
        # Arrange
        branch = "task/issue-42"
        reason = "Waiting for dependency"
        actor = "test-actor"
        mock_github_client.get_issue_body.return_value = "Test issue body"

        # Act
        service.block_flow(branch=branch, reason=reason, actor=actor)

        # Assert - Issue state transition
        mock_label_service.transition.assert_called_once_with(
            42, IssueState.BLOCKED, "test-actor", force=False
        )

        # Assert - Comment added
        mock_github_client.add_comment.assert_called_once_with(
            42, "Flow blocked: Waiting for dependency"
        )

        # Assert - Flow state updated (existing behavior)
        mock_store.update_flow_state.assert_called_once()
        update_kwargs = mock_store.update_flow_state.call_args[1]
        assert update_kwargs["blocked_reason"] == reason
        assert update_kwargs["latest_actor"] == actor

    def test_block_flow_without_issue_number(
        self, service: FlowService, mock_store, mock_label_service, mock_github_client
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
        mock_label_service.transition.assert_not_called()

        # Assert - No comment added (no issue number)
        mock_github_client.add_comment.assert_not_called()

        # Assert - Flow state still updated
        mock_store.update_flow_state.assert_called_once()
        update_kwargs = mock_store.update_flow_state.call_args[1]
        assert update_kwargs["blocked_reason"] == reason
        assert update_kwargs["latest_actor"] == actor

    def test_block_flow_without_reason(
        self, service: FlowService, mock_store, mock_label_service, mock_github_client
    ):
        """block_flow transitions label but doesn't add comment when reason is None."""
        # Arrange
        branch = "task/issue-42"
        reason = None
        actor = "test-actor"
        mock_github_client.get_issue_body.return_value = "Test issue body"

        # Act
        service.block_flow(branch=branch, reason=reason, actor=actor)

        # Assert - Issue state transition still happens
        mock_label_service.transition.assert_called_once_with(
            42, IssueState.BLOCKED, "test-actor", force=False
        )

        # Assert - No comment added (reason is None)
        mock_github_client.add_comment.assert_not_called()

        # Assert - Flow state updated with None reason
        mock_store.update_flow_state.assert_called_once()
        update_kwargs = mock_store.update_flow_state.call_args[1]
        assert update_kwargs["blocked_reason"] is None
        assert update_kwargs["latest_actor"] == actor
