"""Tests for flow usecase orchestration."""

from unittest.mock import MagicMock

import pytest

from vibe3.models.flow import CreateDecision, FlowState
from vibe3.services.flow_usecase import FlowUsecase, FlowUsecaseError
from vibe3.services.spec_ref_service import SpecRefInfo


def test_add_flow_binds_refs_and_ensures_handoff() -> None:
    """Add flow should orchestrate bindings via existing services."""
    flow_service = MagicMock()
    task_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = None
    flow_service.create_flow.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
    )
    handoff_service = MagicMock()
    spec_ref_service = MagicMock()
    spec_ref_service.parse_spec_ref.return_value = SpecRefInfo(
        raw="248",
        kind="issue",
        issue_number=248,
        issue_title="Task title",
        display="#248:Task title",
    )

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=handoff_service,
        spec_ref_service=spec_ref_service,
    )

    result = usecase.add_flow("demo", task="248", spec="docs/plans/demo.md")

    assert result.branch == "task/demo"
    task_service.link_issue.assert_called_once_with(
        "task/demo", 248, "task", actor=None
    )
    flow_service.bind_spec.assert_called_once_with(
        "task/demo", "docs/plans/demo.md", None
    )
    handoff_service.ensure_current_handoff.assert_called_once_with()


def test_add_flow_parses_issue_number_from_issuecomment_url() -> None:
    """Issue parsing should ignore issuecomment suffix when binding task."""
    flow_service = MagicMock()
    task_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = None
    flow_service.create_flow.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
    )
    handoff_service = MagicMock()
    spec_ref_service = MagicMock()
    spec_ref_service.parse_spec_ref.return_value = SpecRefInfo(
        raw="248",
        kind="issue",
        issue_number=248,
        issue_title="Task title",
        display="#248:Task title",
    )

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=handoff_service,
        spec_ref_service=spec_ref_service,
    )

    usecase.add_flow(
        "demo",
        task="https://github.com/jacobcy/vibe-coding-control-center/issues/248#issuecomment-12345",
    )

    task_service.link_issue.assert_called_once_with(
        "task/demo", 248, "task", actor=None
    )


def test_create_flow_uses_decision_start_ref_and_binds_task() -> None:
    """Create flow should reuse service governance decision and bindings."""
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
        raw="248",
        kind="issue",
        issue_number=248,
        issue_title="Task title",
        display="#248:Task title",
    )

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=handoff_service,
        spec_ref_service=spec_ref_service,
    )

    result = usecase.create_flow("demo", base="main", task="248")

    assert result.branch == "task/demo"
    flow_service.create_flow_with_branch.assert_called_once_with(
        slug="demo",
        start_ref="origin/main",
        actor=None,
    )
    task_service.link_issue.assert_called_once_with(
        "task/demo", 248, "task", actor=None
    )
    flow_service.bind_spec.assert_called_once_with(
        "task/demo",
        "#248:Task title",
        None,
    )
    handoff_service.ensure_current_handoff.assert_called_once_with()


def test_create_flow_supports_multiple_task_refs() -> None:
    """Create flow should bind multiple task refs and keep first as primary task."""
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
    flow_service.store = MagicMock()
    task_service.link_issue.side_effect = [
        MagicMock(issue_number=281, issue_role="task", branch="task/demo"),
        MagicMock(issue_number=282, issue_role="task", branch="task/demo"),
    ]
    handoff_service = MagicMock()
    spec_ref_service = MagicMock()
    spec_ref_service.parse_spec_ref.return_value = SpecRefInfo(
        raw="281",
        kind="issue",
        issue_number=281,
        issue_title="Primary task",
        display="#281:Primary task",
    )

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=handoff_service,
        spec_ref_service=spec_ref_service,
    )

    usecase.create_flow("demo", base="main", task=["281", "282"])

    assert task_service.link_issue.call_args_list[0].args == ("task/demo", 281, "task")
    assert task_service.link_issue.call_args_list[1].args == ("task/demo", 282, "task")
    flow_service.store.update_flow_state.assert_called_once_with(
        "task/demo",
        task_issue_number=281,
    )
    flow_service.bind_spec.assert_called_once_with(
        "task/demo",
        "#281:Primary task",
        None,
    )


def test_create_flow_rejects_invalid_task_before_branch_creation() -> None:
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "main"
    flow_service.can_create_from_current_worktree.return_value = CreateDecision(
        allowed=True,
        reason="No active flow in current worktree",
        start_ref="origin/main",
        requires_new_worktree=False,
    )
    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=MagicMock(),
        handoff_service=MagicMock(),
        spec_ref_service=MagicMock(),
    )

    with pytest.raises(ValueError, match="Invalid issue format: abc"):
        usecase.create_flow("demo", base="main", task="abc")

    flow_service.create_flow_with_branch.assert_not_called()


def test_task_derived_spec_ref_is_skipped_when_display_unavailable() -> None:
    """Task-based spec binding should be skipped when display cannot be resolved."""
    flow_service = MagicMock()
    task_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = None
    flow_service.create_flow.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
    )
    spec_ref_service = MagicMock()
    spec_ref_service.parse_spec_ref.return_value = SpecRefInfo(
        raw="248",
        kind="issue",
        issue_number=248,
        issue_title=None,
        display=None,
    )

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=MagicMock(),
        spec_ref_service=spec_ref_service,
    )

    usecase.add_flow("demo", task="248")

    task_service.link_issue.assert_called_once_with(
        "task/demo", 248, "task", actor=None
    )
    flow_service.bind_spec.assert_not_called()


def test_explicit_spec_takes_precedence_over_task_derived_spec() -> None:
    """Explicit spec should not be overwritten by task-derived spec_ref."""
    flow_service = MagicMock()
    task_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = None
    flow_service.create_flow.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
    )
    spec_ref_service = MagicMock()
    spec_ref_service.parse_spec_ref.return_value = SpecRefInfo(
        raw="248",
        kind="issue",
        issue_number=248,
        issue_title="Task title",
        display="#248:Task title",
    )

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=MagicMock(),
        spec_ref_service=spec_ref_service,
    )

    usecase.add_flow("demo", task="248", spec="docs/specs/explicit.md")

    task_service.link_issue.assert_called_once_with(
        "task/demo", 248, "task", actor=None
    )
    flow_service.bind_spec.assert_called_once_with(
        "task/demo",
        "docs/specs/explicit.md",
        None,
    )


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
