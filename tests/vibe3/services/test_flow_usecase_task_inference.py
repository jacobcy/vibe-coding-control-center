"""Tests for flow create task inference from flow name."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.flow import CreateDecision, FlowState
from vibe3.services.flow_usecase import FlowUsecase
from vibe3.services.spec_ref_service import SpecRefInfo


def _build_usecase() -> tuple[FlowUsecase, MagicMock, MagicMock]:
    flow_service = MagicMock()
    task_service = MagicMock()
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
    spec_ref_service = MagicMock()
    spec_ref_service.parse_spec_ref.return_value = SpecRefInfo(
        raw="465",
        kind="issue",
        issue_number=465,
        issue_title="Auto task",
        display="#465:Auto task",
    )
    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=handoff_service,
        spec_ref_service=spec_ref_service,
    )
    return usecase, flow_service, task_service


@pytest.mark.parametrize(
    "name",
    [
        "issue465",
        "issue-465",
        "issue_465",
        "task465",
        "task-465",
        "task_465",
        "task/465",
        "task/issue465",
        "task/issue-465",
        "task/issue_465",
    ],
)
def test_create_flow_infers_task_from_flow_name(name: str) -> None:
    """Create flow should infer task issue from supported name shorthand."""
    usecase, _flow_service, task_service = _build_usecase()

    usecase.create_flow(name, base="main")

    task_service.link_issue.assert_called_once_with(
        f"task/{name}",
        465,
        "task",
        actor=None,
    )


def test_create_flow_explicit_task_takes_precedence_over_name_inference() -> None:
    """Explicit --task should override any task number inferred from flow name."""
    usecase, _flow_service, task_service = _build_usecase()

    usecase.create_flow("issue465", base="main", task="999")

    task_service.link_issue.assert_called_once_with(
        "task/issue465",
        999,
        "task",
        actor=None,
    )


def test_create_flow_skips_binding_when_name_has_no_supported_task_pattern() -> None:
    """No task shorthand in flow name should not trigger implicit task binding."""
    usecase, _flow_service, task_service = _build_usecase()

    usecase.create_flow("feature-login-refactor", base="main")

    task_service.link_issue.assert_not_called()
