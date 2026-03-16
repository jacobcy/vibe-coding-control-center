"""Flow UI rendering."""
from rich import print
from rich.table import Table
from vibe3.models.flow import FlowState, FlowStatusResponse


def render_flow_created(flow: FlowState, task_id: str | None = None) -> None:
    """Render flow creation success message.

    Args:
        flow: Created flow state
        task_id: Optional task ID that was bound
    """
    print(f"[green]✓ Flow created:[/] {flow.flow_slug}")
    print(f"  [cyan]Branch:[/] {flow.branch}")
    if task_id:
        print(f"  [cyan]Task:[/] {task_id}")


def render_flow_bound(flow: FlowState, task_id: str) -> None:
    """Render task binding success message.

    Args:
        flow: Updated flow state
        task_id: Task ID that was bound
    """
    print(f"[green]✓ Task bound to flow:[/] {flow.flow_slug}")
    print(f"  [cyan]Task:[/] {task_id}")


def render_flow_status(status: FlowStatusResponse) -> None:
    """Render flow status details.

    Args:
        status: Flow status response
    """
    print(f"[cyan]Flow:[/] {status.flow_slug}")
    print(f"  [cyan]Branch:[/] {status.branch}")
    print(f"  [cyan]Status:[/] {status.flow_status}")
    if status.task_issue_number:
        print(f"  [cyan]Task Issue:[/] #{status.task_issue_number}")
    if status.pr_number:
        print(f"  [cyan]PR:[/] #{status.pr_number}")
    if status.spec_ref:
        print(f"  [cyan]Spec:[/] {status.spec_ref}")
    if status.next_step:
        print(f"  [cyan]Next Step:[/] {status.next_step}")
    if status.issues:
        issue_list = ', '.join(f'#{i.issue_number}' for i in status.issues)
        print(f"  [cyan]Issues:[/] {issue_list}")


def render_flow_status_table(status: FlowStatusResponse) -> None:
    """Render flow status as a table.

    Args:
        status: Flow status response
    """
    table = Table(title="Flow Status")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Flow", status.flow_slug)
    table.add_row("Branch", status.branch)
    table.add_row("Status", status.flow_status)
    if status.task_issue_number:
        table.add_row("Task Issue", f"#{status.task_issue_number}")
    if status.pr_number:
        table.add_row("PR", f"#{status.pr_number}")
    if status.spec_ref:
        table.add_row("Spec", status.spec_ref)
    if status.next_step:
        table.add_row("Next Step", status.next_step)

    print(table)


def render_flows_table(flows: list[FlowState]) -> None:
    """Render flows list as a table.

    Args:
        flows: List of flow states
    """
    table = Table(title="Flows")
    table.add_column("Flow", style="cyan")
    table.add_column("Branch", style="green")
    table.add_column("Status", style="yellow")

    for flow in flows:
        table.add_row(flow.flow_slug, flow.branch, flow.flow_status)

    print(table)


def render_no_flow(branch: str) -> None:
    """Render no flow found message.

    Args:
        branch: Branch name
    """
    print(f"[yellow]No flow found for branch:[/] {branch}")


def render_no_active_flow() -> None:
    """Render no active flow message."""
    print("[yellow]No active flow[/]")


def render_no_flows() -> None:
    """Render no flows found message."""
    print("[yellow]No flows found[/]")


def render_error(message: str) -> None:
    """Render error message.

    Args:
        message: Error message to display
    """
    print(f"[red]✗ {message}[/]")
