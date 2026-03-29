"""Tests for flow create auto-close behavior in FlowUsecase."""

from unittest.mock import MagicMock

import pytest

from vibe3.exceptions import UserError
from vibe3.models.flow import CreateDecision, FlowState, FlowStatusResponse
from vibe3.services.flow_usecase import FlowUsecase, FlowUsecaseError


def test_create_flow_auto_closes_current_flow_when_pr_already_merged() -> None:
    """Active flow with merged PR should auto-close before creating new flow."""
    flow_service = MagicMock()
    flow_service.get_current_branch.side_effect = ["task/old-flow", "main"]
    flow_service.can_create_from_current_worktree.side_effect = [
        CreateDecision(
            allowed=False,
            reason="Current flow is active - cannot create new flow in same worktree",
            requires_new_worktree=True,
            guidance="Use 'vibe3 wtnew <name>' to create a new worktree",
        ),
        CreateDecision(
            allowed=True,
            reason="No active flow in current worktree",
            start_ref="origin/main",
            requires_new_worktree=False,
        ),
    ]
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/old-flow",
        flow_slug="old-flow",
        flow_status="active",
        task_issue_number=313,
        issues=[],
    )
    flow_service.create_flow_with_branch.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
    )

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=MagicMock(),
        handoff_service=MagicMock(),
    )

    usecase.create_flow("demo", base="main")

    flow_service.close_flow.assert_called_once_with("task/old-flow", check_pr=True)
    flow_service.create_flow_with_branch.assert_called_once_with(
        slug="demo",
        start_ref="origin/main",
        actor=None,
    )


def test_create_flow_keeps_old_rejection_when_auto_close_not_done_eligible() -> None:
    """If auto-close check fails, create should keep original wtnew guidance."""
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/active-flow"
    flow_service.can_create_from_current_worktree.return_value = CreateDecision(
        allowed=False,
        reason="Current flow is active - cannot create new flow in same worktree",
        requires_new_worktree=True,
        guidance="Use 'vibe3 wtnew <name>' to create a new worktree",
    )
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/active-flow",
        flow_slug="active-flow",
        flow_status="active",
        task_issue_number=313,
        issues=[],
    )
    flow_service.close_flow.side_effect = UserError("PR not merged")

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=MagicMock(),
        handoff_service=MagicMock(),
    )

    with pytest.raises(FlowUsecaseError) as exc_info:
        usecase.create_flow("demo")

    assert "active" in str(exc_info.value)
    assert exc_info.value.guidance is not None
    assert "wtnew" in exc_info.value.guidance
    flow_service.close_flow.assert_called_once_with("task/active-flow", check_pr=True)
