"""Tests for issue_branch_resolver conflict detection."""

from unittest.mock import Mock

import pytest

from vibe3.exceptions import UserError
from vibe3.services import (
    _format_flow_details,
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


def test_all_aborted_flows_error(mock_flow_service: Mock, mock_store: Mock):
    """Test error when all flows are aborted."""
    # Arrange: All flows aborted
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "task/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
        {
            "branch": "dev/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
    ]

    # Act & Assert: Should raise UserError with restore hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    error_message = str(exc_info.value)
    assert "All flows for issue" in error_message
    assert "aborted" in error_message
    assert "vibe3 flow restore" in error_message


def test_no_binding_with_candidates_error(mock_flow_service: Mock, mock_store: Mock):
    """Test error when no binding but unbound candidates exist."""
    # Arrange: No flows by issue, but unbound candidate exists
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = {
        "branch": "dev/issue-976",
        "flow_status": "active",
        "pr_ref": None,
    }

    # Act & Assert: Should raise UserError with bind hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    error_message = str(exc_info.value)
    assert "without task binding" in error_message
    assert "vibe3 flow bind" in error_message


def test_no_flows_at_all_error(mock_flow_service: Mock, mock_store: Mock):
    """Test error when no flows exist at all."""
    # Arrange: No flows anywhere
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = None

    # Act & Assert: Should raise UserError with vibe-new hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service)

    error_message = str(exc_info.value)
    assert "No flow found" in error_message
    assert "/vibe-new" in error_message


def test_format_flow_details_with_pr():
    """Test _format_flow_details formats flow with PR correctly."""
    flow = {
        "branch": "dev/issue-976",
        "flow_status": "active",
        "pr_ref": "https://github.com/jacobcy/vibe-center/pull/990",
    }

    result = _format_flow_details(flow)

    assert result == "dev/issue-976 (status: active, pr: #990)"


def test_format_flow_details_without_pr():
    """Test _format_flow_details formats flow without PR correctly."""
    flow = {
        "branch": "task/issue-976",
        "flow_status": "aborted",
        "pr_ref": None,
    }

    result = _format_flow_details(flow)

    assert result == "task/issue-976 (status: aborted, pr: none)"


# Tests for allow_no_flow parameter


def test_allow_no_flow_returns_none_when_no_flows(
    mock_flow_service: Mock, mock_store: Mock
):
    """Test allow_no_flow=True returns None when no flows exist at all."""
    # Arrange: No flows anywhere
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = None

    # Act: With allow_no_flow=True, should return None instead of raising
    result = resolve_issue_branch_input("976", mock_flow_service, allow_no_flow=True)

    # Assert: Returns None (no flow, but no error)
    assert result is None


def test_allow_no_flow_still_raises_all_aborted(
    mock_flow_service: Mock, mock_store: Mock
):
    """Test allow_no_flow=True still raises UserError when all flows are aborted."""
    # Arrange: All flows aborted
    mock_store.get_flows_by_issue.return_value = [
        {
            "branch": "task/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
        {
            "branch": "dev/issue-976",
            "flow_status": "aborted",
            "pr_ref": None,
        },
    ]

    # Act & Assert: Should still raise UserError with restore hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service, allow_no_flow=True)

    error_message = str(exc_info.value)
    assert "All flows for issue" in error_message
    assert "aborted" in error_message
    assert "vibe3 flow restore" in error_message


def test_allow_no_flow_still_raises_conflict(mock_flow_service: Mock, mock_store: Mock):
    """Test allow_no_flow=True still raises UserError for multiple active flows."""
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

    # Act & Assert: Should still raise UserError with conflict hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service, allow_no_flow=True)

    error_message = str(exc_info.value)
    assert "Multiple active flows detected" in error_message
    assert "vibe3 flow abort" in error_message


def test_allow_no_flow_still_raises_unbound_candidates(
    mock_flow_service: Mock, mock_store: Mock
):
    """Test allow_no_flow=True still raises UserError when unbound candidates exist."""
    # Arrange: No flows by issue, but unbound candidate exists
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = {
        "branch": "dev/issue-976",
        "flow_status": "active",
        "pr_ref": None,
    }

    # Act & Assert: Should still raise UserError with bind hint
    with pytest.raises(UserError) as exc_info:
        resolve_issue_branch_input("976", mock_flow_service, allow_no_flow=True)

    error_message = str(exc_info.value)
    assert "without task binding" in error_message
    assert "vibe3 flow bind" in error_message
