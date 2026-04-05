"""Tests for numeric issue-to-branch resolution helpers."""

from unittest.mock import MagicMock

import pytest

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


def test_resolve_issue_branch_input_raises_when_issue_branch_missing() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_state.return_value = None

    with pytest.raises(RuntimeError, match="436"):
        resolve_issue_branch_input("436", flow_service)
