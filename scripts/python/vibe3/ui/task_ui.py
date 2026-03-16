"""Task UI rendering."""
from rich import print
from vibe3.models.flow import FlowState, IssueLink


def render_issue_linked(link: IssueLink) -> None:
    """Render issue linking success message.

    Args:
        link: Created issue link
    """
    print("[green]✓ Issue linked to flow[/]")
    print(f"  [cyan]Issue:[/] #{link.issue_number}")
    print(f"  [cyan]Role:[/] {link.issue_role}")
    print(f"  [cyan]Branch:[/] {link.branch}")


def render_no_active_task() -> None:
    """Render no active task message."""
    print("[yellow]No active task[/]")


def render_task_details(flow_state: FlowState) -> None:
    """Render task details.

    Args:
        flow_state: Flow state representing the task
    """
    print(f"[cyan]Task:[/] {flow_state.flow_slug}")
    print(f"  [cyan]Branch:[/] {flow_state.branch}")
    print(f"  [cyan]Status:[/] {flow_state.flow_status}")
    if flow_state.task_issue_number:
        print(f"  [cyan]Issue:[/] #{flow_state.task_issue_number}")
    if flow_state.next_step:
        print(f"  [cyan]Next Step:[/] {flow_state.next_step}")
