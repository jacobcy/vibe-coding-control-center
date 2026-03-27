"""Tests for task usecase orchestration."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.project_item import ProjectItemError
from vibe3.models.task_bridge import HydrateError
from vibe3.services.task_usecase import TaskUsecase


def test_parse_issue_ref_accepts_github_url() -> None:
    """Issue parsing should support GitHub issue URLs."""
    assert TaskUsecase.parse_issue_ref("https://github.com/acme/repo/issues/248") == 248


def test_show_task_returns_local_fallback_on_hydrate_error() -> None:
    """Show task should keep local fallback when remote hydrate fails softly."""
    flow_service = MagicMock()
    task_service = MagicMock()
    task_service.hydrate.return_value = HydrateError(
        type="no_remote_identity",
        message="not bound",
    )
    task_service.get_task.return_value = MagicMock(branch="task/demo")
    usecase = TaskUsecase(flow_service=flow_service, task_service=task_service)

    result = usecase.show_task("task/demo")

    assert result.hydrate_error is not None
    assert result.local_task is task_service.get_task.return_value


def test_link_issue_uses_current_branch_and_parsed_issue_number() -> None:
    """Link issue should reuse branch resolution and TaskService.link_issue."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    task_service = MagicMock()
    usecase = TaskUsecase(flow_service=flow_service, task_service=task_service)

    usecase.link_issue("#219", "dependency")

    task_service.link_issue.assert_called_once_with("task/demo", 219, "dependency")


def test_update_remote_status_returns_branch_and_result() -> None:
    """Remote status update should preserve branch for command output."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    task_service = MagicMock()
    task_service.update_remote_task_status.return_value = ProjectItemError(
        type="network_error",
        message="timeout",
    )
    usecase = TaskUsecase(flow_service=flow_service, task_service=task_service)

    branch, result = usecase.update_remote_status("Done")

    assert branch == "task/demo"
    assert isinstance(result, ProjectItemError)


def test_parse_issue_ref_rejects_invalid_reference() -> None:
    """Invalid issue references should still fail fast."""
    with pytest.raises(ValueError):
        TaskUsecase.parse_issue_ref("not-an-issue")
