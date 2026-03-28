"""Task UI rendering."""

from typing import Any

from vibe3.models.flow import FlowState
from vibe3.ui.console import console
from vibe3.ui.flow_ui import render_milestone


def render_no_active_task() -> None:
    console.print("[yellow]no active task[/]")


def render_task_details(flow_state: FlowState) -> None:
    console.print(f"\n[bold]{flow_state.flow_slug}[/]")
    console.print(f"  branch  {flow_state.branch}")
    console.print(f"  status  {flow_state.flow_status}")
    if flow_state.task_issue_number:
        console.print(f"  issue   #{flow_state.task_issue_number}")
    if flow_state.next_step:
        console.print(f"  next    {flow_state.next_step}")


def render_task_milestone(
    task_issue_number: int, milestone_data: dict[str, Any]
) -> None:
    """Render milestone orchestration context for a task."""
    render_milestone(milestone_data, task_issue_number)
