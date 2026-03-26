"""Flow UI rendering."""

from rich.text import Text

from vibe3.models.flow import FlowEvent, FlowState, FlowStatusResponse
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
    """flow show — full detail, YAML style (branch-centric)."""
    titles = issue_titles or {}
    # Branch as primary key with flow status
    status_text = _status_text(status.flow_status).plain
    console.print(f"[cyan bold]{status.branch}[/]  [dim](Flow: {status_text})[/]")
    _kv("flow_slug", status.flow_slug, 1)

    # issues with titles
    if status.task_issue_number:
        n = status.task_issue_number
        title = titles.get(n, "")
        suffix = f"  [dim]{title}[/]" if title else ""
        console.print(f"  [dim]task_issue:[/] #{n}{suffix}")
    if status.issues:
        related_issues = [i for i in status.issues if i.issue_role == "related"]
        dependency_issues = [i for i in status.issues if i.issue_role == "dependency"]
        if related_issues:
            console.print("  [dim]related_issues:[/]")
            for i in related_issues:
                title = titles.get(i.issue_number, "")
                suffix = f"  [dim]{title}[/]" if title else ""
                console.print(f"    - #{i.issue_number}{suffix}")
        if dependency_issues:
            console.print("  [dim]dependencies:[/]")
            for i in dependency_issues:
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
    else:
        console.print(
            "  [dim]pr:[/] [yellow]—[/]  "
            "[dim][hint: run `vibe3 check --fix` to detect][/]"
        )

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

    # execution status
    execution_statuses = [
        ("planner", status.planner_status),
        ("executor", status.executor_status),
        ("reviewer", status.reviewer_status),
    ]
    has_execution = any(s for _, s in execution_statuses)
    if has_execution:
        console.print("  [dim]execution:[/]")
        for role, st in execution_statuses:
            if st:
                icon = {
                    "running": "⏳",
                    "done": "✓",
                    "crashed": "✗",
                    "pending": "○",
                }.get(st, "?")
                color = {"running": "yellow", "done": "green", "crashed": "red"}.get(
                    st, "dim"
                )
                console.print(f"    [{color}]{icon} {role}: {st}[/]")
        if status.execution_started_at:
            _kv("started", status.execution_started_at[:19], 2)
        if status.execution_pid:
            _kv("pid", status.execution_pid, 2)

    console.print()


def render_flow_status_table(status: FlowStatusResponse) -> None:
    """Alias kept for compatibility."""
    render_flow_status(status)


def render_flows_table(flows: list[FlowState]) -> None:
    """flow list — YAML style, one block per flow (branch-centric)."""
    for flow in flows:
        task_str = f"#{flow.task_issue_number}" if flow.task_issue_number else "—"
        # Branch as primary key with flow status
        status_text = _status_text(flow.flow_status).plain
        console.print(f"[cyan]{flow.branch}[/]  [dim](Flow: {status_text})[/]")
        _kv("flow_slug", flow.flow_slug, 1)
        _kv("task_issue", task_str, 1)
        console.print()


def render_flows_status_dashboard(
    flows: list[FlowState], titles: dict[int, str]
) -> None:
    """flow status dashboard — YAML style with remote title (branch-centric)."""
    for flow in flows:
        task_num = flow.task_issue_number
        task_str = f"#{task_num}" if task_num else "—"
        title = titles.get(task_num, "—") if task_num else "—"
        # Branch as primary key with flow status
        status_text = _status_text(flow.flow_status).plain
        console.print(f"[cyan]{flow.branch}[/]  [dim](Flow: {status_text})[/]")
        _kv("flow_slug", flow.flow_slug, 1)
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


_EVENT_COLOR: dict[str, str] = {
    "flow_created": "cyan",
    "task_bound": "cyan",
    "issue_linked": "cyan",
    "status_updated": "dim",
    "next_step_set": "dim",
    "pr_created": "yellow",
    "pr_ready": "yellow",
    "pr_merged": "green",
    "run_started": "yellow",
    "run_completed": "green",
    "run_aborted": "red",
    "plan_started": "yellow",
    "plan_completed": "green",
    "plan_aborted": "red",
    "review_started": "yellow",
    "review_completed": "green",
    "review_aborted": "red",
    "planner_started": "yellow",
    "planner_completed": "green",
    "planner_aborted": "red",
    "executor_started": "yellow",
    "executor_completed": "green",
    "executor_aborted": "red",
    "executor_cancelled": "red",
    "reviewer_started": "yellow",
    "reviewer_completed": "green",
    "reviewer_aborted": "red",
    "handoff_plan": "blue",
    "handoff_run": "blue",
    "handoff_review": "magenta",
}


def render_flow_timeline(state: FlowState, events: list[FlowEvent]) -> None:
    # Branch as primary key with flow status
    status_text = _status_text(state.flow_status).plain
    console.print(f"[bold cyan]{state.branch}[/]  [dim](Flow: {status_text})[/]")
    _kv("flow_slug", state.flow_slug, 1)
    if state.task_issue_number:
        console.print(f"  [dim]task[/]        #{state.task_issue_number}")
    else:
        console.print(
            "  [yellow]task[/]        [dim]not bound[/]  "
            "[dim]→ vibe3 flow bind <task-id>[/]"
        )
    if state.pr_number:
        console.print(f"  [dim]pr[/]          #{state.pr_number}")
    if state.spec_ref:
        console.print(f"  [dim]spec[/]        {state.spec_ref}")
    if state.next_step:
        console.print(f"  [dim]next[/]        {state.next_step}")
    console.print()

    if not events:
        console.print("[dim]  no events[/]")
        return

    console.print("[bold]═══ Timeline ═══[/]")
    console.print()

    for event in reversed(events):
        color = _EVENT_COLOR.get(event.event_type, "white")
        time_str = event.created_at[:16].replace("T", " ")
        actor_short = event.actor
        console.print(
            f"[dim]{time_str}[/]  [{color}]{event.event_type}[/]  [dim]{actor_short}[/]"
        )
        if event.detail:
            console.print(f"  {event.detail}")
        if event.refs:
            files = event.refs.get("files") if isinstance(event.refs, dict) else None
            if files and isinstance(files, list):
                for f in files:
                    console.print(f"  [dim]📎 {f}[/]")
            ref = event.refs.get("ref") if isinstance(event.refs, dict) else None
            if ref:
                console.print(f"  [dim]📎 {ref}[/]")
        console.print()

    refs_shown = False
    for label in ["spec_ref", "plan_ref", "report_ref", "audit_ref"]:
        val = getattr(state, label, None)
        if val:
            if not refs_shown:
                console.print("[bold]═══ Refs ═══[/]")
                refs_shown = True
            actor_field = label.replace("_ref", "_actor")
            actor = getattr(state, actor_field, None) or ""
            actor_str = f"  [dim]{actor}[/]" if actor else ""
            console.print(f"  [dim]{label}[/]  {val}{actor_str}")
    console.print()
