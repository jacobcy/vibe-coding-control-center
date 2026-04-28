"""Tests for numeric issue-to-branch resolution helpers."""

from unittest.mock import MagicMock

from vibe3.utils.issue_branch_resolver import resolve_issue_branch_input


def test_resolve_issue_branch_input_prefers_task_branch() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_state.side_effect = lambda branch: (
        {"branch": branch} if branch == "task/issue-436" else None
    )

    result = resolve_issue_branch_input("436", flow_service)

    assert result == "task/issue-436"


def test_resolve_issue_branch_input_falls_back_to_dev_branch() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_state.side_effect = lambda branch: (
        {"branch": branch} if branch == "dev/issue-436" else None
    )

    result = resolve_issue_branch_input("436", flow_service)

    assert result == "dev/issue-436"


def test_resolve_issue_branch_input_preserves_non_numeric_branch() -> None:
    flow_service = MagicMock()

    result = resolve_issue_branch_input("task/issue-436", flow_service)

    assert result == "task/issue-436"
    flow_service.get_flow_state.assert_not_called()


def test_resolve_issue_branch_input_returns_original_when_issue_branch_missing() -> (
    None
):
    """Test that the function returns original input instead of raising error.

    This allows task show/status to query issue state even without flow.
    """
    flow_service = MagicMock()
    flow_service.get_flow_state.return_value = None

    result = resolve_issue_branch_input("436", flow_service)
    assert result == "436"
