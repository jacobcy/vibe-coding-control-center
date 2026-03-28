"""Idempotent flow-add behavior tests for FlowUsecase."""

from unittest.mock import MagicMock

from vibe3.models.flow import FlowState, FlowStatusResponse
from vibe3.services.flow_usecase import FlowUsecase


def test_add_flow_existing_branch_updates_actor_without_recreate() -> None:
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=248,
        latest_actor="codex/gpt-5.4",
    )
    flow_service.get_flow_state.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=248,
        latest_actor="claude/sonnet-4.6",
    )
    flow_service.store = MagicMock()

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=MagicMock(),
        handoff_service=MagicMock(),
    )

    result = usecase.add_flow("demo", actor="claude/sonnet-4.6")

    assert result.latest_actor == "claude/sonnet-4.6"
    flow_service.create_flow.assert_not_called()
    flow_service.store.update_flow_state.assert_any_call(
        "task/demo", latest_actor="claude/sonnet-4.6"
    )


def test_add_flow_existing_branch_appends_tasks_but_keeps_primary() -> None:
    flow_service = MagicMock()
    flow_service.get_current_branch.return_value = "task/demo"
    flow_service.get_flow_status.return_value = FlowStatusResponse(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=248,
        latest_actor="codex/gpt-5.4",
    )
    flow_service.get_flow_state.return_value = FlowState(
        branch="task/demo",
        flow_slug="demo",
        flow_status="active",
        task_issue_number=248,
        latest_actor="codex/gpt-5.4",
    )
    flow_service.store = MagicMock()

    task_service = MagicMock()
    task_service.link_issue.side_effect = [
        MagicMock(issue_number=281, issue_role="task", branch="task/demo"),
        MagicMock(issue_number=282, issue_role="task", branch="task/demo"),
    ]

    usecase = FlowUsecase(
        flow_service=flow_service,
        task_service=task_service,
        handoff_service=MagicMock(),
    )

    usecase.add_flow("demo", task=["281", "282"])

    first_call = task_service.link_issue.call_args_list[0]
    second_call = task_service.link_issue.call_args_list[1]
    assert first_call.args == ("task/demo", 281, "task")
    assert first_call.kwargs == {"actor": "codex/gpt-5.4"}
    assert second_call.args == ("task/demo", 282, "task")
    assert second_call.kwargs == {"actor": "codex/gpt-5.4"}
    flow_service.store.update_flow_state.assert_any_call(
        "task/demo",
        task_issue_number=248,
    )


def test_bind_issue_delegates_to_task_service() -> None:
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
    task_service.link_issue.assert_called_once_with(
        "task/demo", 248, "dependency", actor=None
    )
