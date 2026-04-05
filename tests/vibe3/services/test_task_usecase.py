"""Tests for Task usecase."""

from unittest.mock import MagicMock

import pytest

from vibe3.services.task_usecase import TaskUsecase


def test_show_task_returns_local_data() -> None:
    """Show task should return local flow state and links."""
    flow_service = MagicMock()
    task_service = MagicMock()

    mock_task = MagicMock(branch="task/demo")
    task_service.get_task.return_value = mock_task

    flow_service.store.get_issue_links.return_value = [
        {"issue_number": 101, "issue_role": "related"},
        {"issue_number": 102, "issue_role": "dependency"},
    ]

    usecase = TaskUsecase(flow_service=flow_service, task_service=task_service)
    result = usecase.show_task("task/demo")

    assert result.branch == "task/demo"
    assert result.local_task == mock_task
    assert result.related_issue_numbers == [101]
    assert result.dependency_issue_numbers == [102]


def test_resolve_branch_converts_numeric_issue_to_task_branch() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_state.side_effect = lambda branch: (
        {"branch": branch} if branch == "task/issue-436" else None
    )
    task_service = MagicMock()

    usecase = TaskUsecase(flow_service=flow_service, task_service=task_service)

    assert usecase.resolve_branch("436") == "task/issue-436"


def test_resolve_branch_raises_for_unknown_numeric_issue() -> None:
    flow_service = MagicMock()
    flow_service.get_flow_state.return_value = None
    task_service = MagicMock()

    usecase = TaskUsecase(flow_service=flow_service, task_service=task_service)

    with pytest.raises(RuntimeError, match="436"):
        usecase.resolve_branch("436")
