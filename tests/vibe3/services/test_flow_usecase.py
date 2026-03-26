"""Tests for flow usecase orchestration."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.flow import CreateDecision, FlowState
from vibe3.services.flow_usecase import FlowUsecase, FlowUsecaseError


def test_add_flow_binds_refs_and_ensures_handoff() -> None:
    """Add flow should orchestrate bindings via existing services."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = None
    flow_service.create_flow.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
    )
    handoff_service = MagicMock()

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=MagicMock(),
        handoff_service=handoff_service,
    )

    result = usecase.add_flow("demo", task="248", spec="docs/plans/demo.md")

    assert result.branch == "task/demo"
    flow_service.bind_task.assert_called_once_with("task/demo", "248", "system")
    flow_service.bind_spec.assert_called_once_with(
        "task/demo", "docs/plans/demo.md", "system"
    )
    handoff_service.ensure_current_handoff.assert_called_once_with()


def test_create_flow_uses_decision_start_ref_and_binds_task() -> None:
    """Create flow should reuse service governance decision and bindings."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "main"
    flow_service.can_create_from_current_worktree.return_value = CreateDecision(
        allowed=True,
        reason="No active flow in current worktree",
        start_ref="origin/main",
        requires_new_worktree=False,
    )
    flow_service.create_flow_with_branch.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
    )
    handoff_service = MagicMock()

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=MagicMock(),
        handoff_service=handoff_service,
    )

    result = usecase.create_flow("demo", base="main", task="248")

    assert result.branch == "task/demo"
    flow_service.create_flow_with_branch.assert_called_once_with(
        slug="demo",
        start_ref="origin/main",
    )
    flow_service.bind_task.assert_called_once_with("task/demo", "248", "system")
    handoff_service.ensure_current_handoff.assert_called_once_with()


def test_create_flow_rejects_invalid_base_current_request() -> None:
    """Create flow should surface governance guidance for invalid base current."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/done"
    flow_service.can_create_from_current_worktree.return_value = CreateDecision(
        allowed=True,
        reason="Current flow is done",
        start_ref="origin/main",
        allow_base_current=False,
        requires_new_worktree=False,
    )

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=MagicMock(),
        handoff_service=MagicMock(),
    )

    with pytest.raises(FlowUsecaseError) as exc_info:
        usecase.create_flow("demo", base="current")

    assert "only allowed when current flow is blocked" in str(exc_info.value)


def test_bind_issue_delegates_to_task_service() -> None:
    """Bind issue should parse refs and delegate to TaskService."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    task_service = MagicMock()
    task_service.link_issue.return_value.branch = "task/demo"
    task_service.link_issue.return_value.issue_number = 248

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=MagicMock(),
    )

    result = usecase.bind_issue("#248", "dependency")

    assert result.issue_number == 248
    task_service.link_issue.assert_called_once_with("task/demo", 248, "dependency")
