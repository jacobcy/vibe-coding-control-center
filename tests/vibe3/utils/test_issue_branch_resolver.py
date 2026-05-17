"""Tests for numeric issue-to-branch resolution helpers."""

from unittest.mock import MagicMock

import pytest

from vibe3.exceptions import UserError
from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input


def test_resolve_issue_branch_input_prefers_task_branch() -> None:
    flow_service = MagicMock()
    flow_service.store.get_flows_by_issue.return_value = [
        {"branch": "task/issue-436", "flow_status": "active"}
    ]

    result = resolve_issue_branch_input("436", flow_service)

    assert result == "task/issue-436"


def test_resolve_issue_branch_input_falls_back_to_dev_branch() -> None:
    flow_service = MagicMock()
    flow_service.store.get_flows_by_issue.return_value = [
        {"branch": "dev/issue-436", "flow_status": "active"}
    ]

    result = resolve_issue_branch_input("436", flow_service)

    assert result == "dev/issue-436"


def test_resolve_issue_branch_input_preserves_non_numeric_branch() -> None:
    flow_service = MagicMock()

    result = resolve_issue_branch_input("task/issue-436", flow_service)

    assert result == "task/issue-436"
    flow_service.get_flow_state.assert_not_called()


def test_resolve_issue_branch_input_no_flow_raises_error() -> None:
    """Test that function raises UserError when no active flow is found.

    Fail-fast: users must have active flow to use numeric issue references.
    """
    flow_service = MagicMock()

    # Mock store to return no flows
    mock_store = MagicMock()
    mock_store.get_flows_by_issue.return_value = []
    mock_store.get_flow_state.return_value = None  # No unbound candidates either
    flow_service.store = mock_store

    with pytest.raises(UserError, match="No flow found for issue #436"):
        resolve_issue_branch_input("436", flow_service)
