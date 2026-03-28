"""Tests for task usecase orchestration."""

from unittest.mock import MagicMock

from vibe3.models.task_bridge import HydrateError
from vibe3.services.task_usecase import TaskUsecase


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
