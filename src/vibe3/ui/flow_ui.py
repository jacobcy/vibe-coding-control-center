"""Flow UI rendering."""

from rich.table import Table
from rich.text import Text

from vibe3.models.flow import FlowState, FlowStatusResponse
from vibe3.ui.console import console

_STATUS_COLOR: dict[str, str] = {
    "active": "green",
    "done": "dim",
    "blocked": "red",
    "stale": "yellow",
}


def _status_text(status: str) -> Text:
    color = _STATUS_COLOR.get(status.lower(), "white")
    return Text(status, style=color)


def render_flow_created(flow: FlowState, task_id: str | None = None) -> None:
    console.print(f"[green]✓[/] Flow created: [cyan]{flow.flow_slug}[/]")
    console.print(f"  branch  {flow.branch}")
    if task_id:
        console.print(f"  task    {task_id}")


def render_flow_bound(flow: FlowState, task_id: str) -> None:
    console.print(f"[green]✓[/] Task bound: [cyan]{flow.flow_slug}[/]")
    console.print(f"  task    {task_id}")


def render_flow_status(status: FlowStatusResponse) -> None:
    """Render flow status as clean key/value lines."""
    console.print(f"\n[bold]{status.flow_slug}[/]  {_status_text(status.flow_status)}")
    console.print(f"  [dim]branch[/]      {status.branch}")
    if status.task_issue_number:
        console.print(f"  [dim]task[/]        #{status.task_issue_number}")
    if status.pr_number:
        console.print(f"  [dim]pr[/]          #{status.pr_number}")
    if status.spec_ref:
        console.print(f"  [dim]spec[/]        {status.spec_ref}")
    if status.next_step:
        console.print(f"  [dim]next[/]        {status.next_step}")
    if status.issues:
        issue_list = "  ".join(f"#{i.issue_number}" for i in status.issues)
        console.print(f"  [dim]issues[/]      {issue_list}")
    console.print()


def render_flow_status_table(status: FlowStatusResponse) -> None:
    """Alias kept for compatibility."""
    render_flow_status(status)


def render_flows_table(flows: list[FlowState]) -> None:
    """Render flows list as a borderless table."""
    table = Table(box=None, pad_edge=False, show_header=True, header_style="bold dim")
    table.add_column("flow", style="cyan", min_width=24)
    table.add_column("branch", style="white", min_width=28)
    table.add_column("status")
    for flow in flows:
        table.add_row(flow.flow_slug, flow.branch, _status_text(flow.flow_status))
    console.print(table)


def render_no_flow(branch: str) -> None:
    console.print(f"[yellow]no flow found[/] for branch: {branch}")


def render_no_active_flow() -> None:
    console.print("[yellow]no active flow[/]")


def render_no_flows() -> None:
    console.print("[yellow]no flows found[/]")


def render_error(message: str) -> None:
    console.print(f"[red]✗[/] {message}")
