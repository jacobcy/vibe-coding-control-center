"""Flow UI rendering."""

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


def _kv(key: str, value: object, indent: int = 0) -> None:
    pad = "  " * indent
    console.print(f"{pad}[dim]{key}:[/] {value}")


def render_flow_created(flow: FlowState, task_id: str | None = None) -> None:
    console.print(f"[green]✓[/] Flow created: [cyan]{flow.flow_slug}[/]")
    _kv("branch", flow.branch, 1)
    if task_id:
        _kv("task", task_id, 1)


def render_flow_bound(flow: FlowState, task_id: str) -> None:
    console.print(f"[green]✓[/] Task bound: [cyan]{flow.flow_slug}[/]")
    _kv("task", task_id, 1)


def render_flow_status(
    status: FlowStatusResponse,
    issue_titles: dict[int, str] | None = None,
    pr_data: dict[str, object] | None = None,
) -> None:
    """flow show — full detail, YAML style."""
    titles = issue_titles or {}
    console.print(
        f"[cyan bold]{status.flow_slug}[/]  {_status_text(status.flow_status)}"
    )
    _kv("branch", status.branch, 1)

    # issues with titles
    if status.task_issue_number:
        n = status.task_issue_number
        title = titles.get(n, "")
        suffix = f"  [dim]{title}[/]" if title else ""
        console.print(f"  [dim]task_issue:[/] #{n}{suffix}")
    if status.issues:
        repo_issues = [i for i in status.issues if i.issue_role == "repo"]
        if repo_issues:
            console.print("  [dim]repo_issues:[/]")
            for i in repo_issues:
                title = titles.get(i.issue_number, "")
                suffix = f"  [dim]{title}[/]" if title else ""
                console.print(f"    - #{i.issue_number}{suffix}")

    # PR
    if pr_data:
        draft_tag = " [dim][draft][/]" if pr_data.get("draft") else ""
        state = str(pr_data.get("state", "")).lower()
        console.print(
            f"  [dim]pr:[/] #{pr_data['number']}{draft_tag}"
            f"  [dim]{state}[/]  {pr_data.get('title', '')}"
        )
        _kv("url", pr_data.get("url", ""), 2)
    elif status.pr_number:
        _kv("pr", f"#{status.pr_number}  [dim](offline)[/]", 1)

    # plan / execute / review
    console.print("  [dim]plan:[/]")
    _kv("actor", status.planner_actor or "—", 2)
    _kv("ref", status.plan_ref or "—", 2)

    console.print("  [dim]execute:[/]")
    _kv("actor", status.executor_actor or "—", 2)
    _kv("ref", status.report_ref or "—", 2)

    console.print("  [dim]review:[/]")
    _kv("actor", status.reviewer_actor or "—", 2)
    _kv("ref", status.audit_ref or "—", 2)

    # misc
    if status.spec_ref:
        _kv("spec", status.spec_ref, 1)
    if status.blocked_by:
        _kv("blocked_by", status.blocked_by, 1)
    if status.next_step:
        _kv("next_step", status.next_step, 1)
    console.print()


def render_flow_status_table(status: FlowStatusResponse) -> None:
    """Alias kept for compatibility."""
    render_flow_status(status)


def render_flows_table(flows: list[FlowState]) -> None:
    """flow list — YAML style, one block per flow."""
    for flow in flows:
        task_str = f"#{flow.task_issue_number}" if flow.task_issue_number else "—"
        console.print(f"[cyan]{flow.flow_slug}[/]  {_status_text(flow.flow_status)}")
        _kv("branch", flow.branch, 1)
        _kv("task_issue", task_str, 1)
        console.print()


def render_flows_status_dashboard(
    flows: list[FlowState], titles: dict[int, str]
) -> None:
    """flow status dashboard — YAML style with remote title."""
    for flow in flows:
        task_num = flow.task_issue_number
        task_str = f"#{task_num}" if task_num else "—"
        title = titles.get(task_num, "—") if task_num else "—"
        console.print(f"[cyan]{flow.flow_slug}[/]  {_status_text(flow.flow_status)}")
        _kv("branch", flow.branch, 1)
        _kv("task_issue", task_str, 1)
        _kv("title", title, 1)
        console.print()


def render_no_flow(branch: str) -> None:
    console.print(f"[yellow]no flow found[/] for branch: {branch}")


def render_no_active_flow() -> None:
    console.print("[yellow]no active flow[/]")


def render_no_flows() -> None:
    console.print("[yellow]no flows found[/]")


def render_error(message: str) -> None:
    console.print(f"[red]✗[/] {message}")
