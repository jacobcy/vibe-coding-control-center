"""Task UI rendering."""

import json
from typing import TYPE_CHECKING

from vibe3.models.flow import FlowStatusResponse
from vibe3.services.milestone_service import MilestoneContext
from vibe3.ui.console import console
from vibe3.ui.flow_ui import render_milestone

if TYPE_CHECKING:
    from vibe3.services.task_usecase import TaskShowResult


def render_no_active_task() -> None:
    console.print("[yellow]no active task[/]")


def render_task_details(flow_state: FlowStatusResponse) -> None:
    console.print(f"\n[bold]{flow_state.flow_slug}[/]")
    console.print(f"  branch  {flow_state.branch}")
    console.print(f"  status  {flow_state.flow_status}")
    if flow_state.task_issue_number:
        console.print(f"  issue   #{flow_state.task_issue_number}")
    if flow_state.next_step:
        console.print(f"  next    {flow_state.next_step}")


def render_task_milestone(
    task_issue_number: int, milestone_data: dict | MilestoneContext
) -> None:
    """Render milestone orchestration context for a task."""
    if isinstance(milestone_data, MilestoneContext):
        milestone_data = {
            "number": milestone_data.number,
            "title": milestone_data.title,
            "open": milestone_data.open_count,
            "closed": milestone_data.closed_count,
            "issues": milestone_data.issues,
            "task_issue": milestone_data.task_issue_number,
        }
    render_milestone(milestone_data, task_issue_number)


def render_task_show(task_result: "TaskShowResult", json_output: bool) -> None:
    """Render task show output.

    Args:
        task_result: Task show query result
        json_output: If True, output as JSON; otherwise formatted text
    """
    if task_result.hydrate_error:
        _render_task_show_error(task_result, json_output)
        return

    if not task_result.view:
        console.print(f"[red]Task not found: {task_result.branch}[/]")
        raise SystemExit(1)

    view = task_result.view
    if json_output:
        console.print(json.dumps(view.model_dump(), indent=2, default=str))
        return

    bound_id = view.project_item_id.value if view.project_item_id else None
    bind_status = "[bound]" if bound_id else "[unbound]"
    console.print(f"Branch: {view.branch}")
    console.print(f"Project Item {bind_status}: {bound_id or 'N/A'}")

    if view.task_issue_number:
        console.print(f"Task Issue: #{view.task_issue_number.value}")
    if task_result.related_issue_numbers:
        console.print(
            "Related Issue(s): "
            + "  ".join(f"#{number}" for number in task_result.related_issue_numbers)
        )
    if task_result.dependency_issue_numbers:
        console.print(
            "Dependencies: "
            + "  ".join(f"#{number}" for number in task_result.dependency_issue_numbers)
        )
    if view.spec_ref:
        console.print(f"Spec Ref: {view.spec_ref.value}")
    if view.next_step:
        console.print(f"Next Step: {view.next_step.value}")
    if view.blocked_by:
        console.print(f"Blocked By: {view.blocked_by.value}")

    if view.offline_mode:
        console.print("[offline mode] 远端读取失败，仅显示本地 bridge 字段")
    else:
        if view.title:
            console.print(f"[remote] Title:    {view.title.value}")
        if view.body:
            console.print(f"[remote] Body:     {view.body.value}")
        if view.status:
            console.print(f"[remote] Status:   {view.status.value}")
        if view.priority:
            console.print(f"[remote] Priority: {view.priority.value}")
        if view.assignees:
            console.print(f"[remote] Assignees: {', '.join(view.assignees.value)}")

    if view.identity_drift:
        console.print("[warning] identity_drift=True: 本地与远端 identity 不一致")


def _render_task_show_error(task_result: "TaskShowResult", json_output: bool) -> None:
    """Render hydrate fallback or hard error for task show."""
    error = task_result.hydrate_error
    if not error:
        return

    if error.type == "binding_invalid":
        console.print(f"[red]Error [{error.type}]: {error.message}[/]")
        raise SystemExit(1)

    task = task_result.local_task
    if not task:
        console.print(f"[red]Task not found: {task_result.branch}[/]")
        raise SystemExit(1)

    if json_output:
        console.print(json.dumps(task.model_dump(), indent=2, default=str))
        return

    console.print(f"Branch: {task.branch}")
    if task.task_issue_number:
        console.print(f"Task Issue: #{task.task_issue_number}")
    console.print(f"Status (local flow): {task.flow_status}")
    console.print(f"[hint] {error.message}")


def render_task_show_with_milestone(
    task_result: "TaskShowResult",
    milestone_context: MilestoneContext | None,
    json_output: bool,
) -> None:
    """Render task show with milestone context.

    Combines render_task_show with milestone rendering.
    """
    render_task_show(task_result, json_output)

    if milestone_context and not json_output:
        render_task_milestone(milestone_context.task_issue_number, milestone_context)


def render_task_show_error_with_milestone(
    task_result: "TaskShowResult",
    milestone_context: MilestoneContext | None,
    json_output: bool,
) -> None:
    """Render task show error with milestone context."""
    _render_task_show_error(task_result, json_output)

    if milestone_context and not json_output:
        render_task_milestone(milestone_context.task_issue_number, milestone_context)
