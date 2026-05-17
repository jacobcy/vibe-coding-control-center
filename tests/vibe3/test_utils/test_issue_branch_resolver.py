"""Tests for issue_branch_resolver conflict detection."""

from typing import Any  # noqa: F401
from unittest.mock import MagicMock, Mock  # noqa: F401

import pytest

from vibe3.exceptions import UserError  # noqa: F401
from vibe3.utils.issue_branch_resolver import (  # noqa: F401
    _format_flow_details,
    _resolve_best_flow_from_candidates,
    resolve_issue_branch_input,
)


@pytest.fixture
def mock_flow_service() -> Mock:
    """Create mock FlowService with store."""
    service = Mock()
    service.store = Mock()
    service.get_flow_state = Mock()
    return service


@pytest.fixture
def mock_store(mock_flow_service: Mock) -> Mock:
    """Get store from mock_flow_service."""
    return mock_flow_service.store


def test_single_non_aborted_flow_auto_select(mock_flow_service: Mock, mock_store: Mock):
    """Test auto-selection when only one non-aborted flow exists."""
    # Arrange: Single active flow with issue binding
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        }
    ]

    # Act: Resolve issue number
    result = resolve_issue_branch_input("976", mock_flow_service)

    # Assert: Returns correct branch
    assert result == "dev/issue-976"
    mock_store.get_flows_by_issue.assert_called_once_with(976, role="task")


def test_multiple_non_aborted_one_active_auto_select(
    mock_flow_service: Mock, mock_store: Mock
):
    """Test auto-selection when one aborted and one active flow exist."""
    # Arrange: One aborted, one active
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "task/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        },
    ]

    # Act: Resolve issue number
    result = resolve_issue_branch_input("976", mock_flow_service)

    # Assert: Returns active branch
    assert result == "dev/issue-976"
    mock_store.get_flows_by_issue.assert_called_once_with(976, role="task")


def test_multiple_active_flows_conflict_error(
    mock_flow_service: Mock, mock_store: Mock
):
    """Test error when multiple active flows exist."""
    # Arrange: Multiple active flows
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "dev/issue-976",
            "flow_status": "active",
            "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
        },
        {
            "branch": "task/issue-976",
            "flow_status": "active",
            "pr_ref": None,
        },
    ]

    # Act & Assert: Should raise UserError with helpful message
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    error_message = str(exc_info.value)
    assert "Multiple active flows detected" in error_message
    assert "vibe3 flow abort" in error_message
