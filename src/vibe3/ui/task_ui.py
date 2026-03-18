"""Task UI rendering."""

from vibe3.models.flow import FlowState, IssueLink
from vibe3.ui.console import console


def render_issue_linked(link: IssueLink) -> None:
    console.print("[green]✓[/] Issue linked to flow")
    console.print(f"  issue   #{link.issue_number}")
    console.print(f"  role    {link.issue_role}")
    console.print(f"  branch  {link.branch}")


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
