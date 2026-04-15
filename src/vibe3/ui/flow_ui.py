"""Flow UI rendering."""

from typing import Any

from vibe3.models.flow import FlowStatusResponse
from vibe3.ui.console import console
from vibe3.ui.flow_ui_primitives import display_actor, kv, status_text
from vibe3.ui.flow_ui_timeline import (  # noqa: F401
    render_flow_timeline,
    render_milestone,
)


def _render_flow_row(
    flow: FlowStatusResponse,
    title: str | None = None,
    pr_data: dict[str, object] | None = None,
    worktree: str | None = None,
) -> None:
    status_str = status_text(flow.flow_status).plain
    console.print(f"[cyan]{flow.branch}[/]  [dim](Flow: {status_str})[/]")
    kv("flow_slug", flow.flow_slug, 1)
    task_str = f"#{flow.task_issue_number}" if flow.task_issue_number else "—"
    kv("task_issue", task_str, 1)
    if title is not None:
        kv("title", title, 1)
    if worktree:
        kv("worktree", worktree, 1)
    if flow.initiated_by:
        kv("initiated_by", flow.initiated_by, 1)
    # Always show actor — fallback to worktree identity when flow has no signature
    _actor, _fallback = display_actor(flow.latest_actor)
    _suffix = " [dim](worktree)[/]" if _fallback else ""
    kv("latest", f"{_actor}{_suffix}", 1)
    if pr_data:
        draft_tag = " [dim][draft][/]" if pr_data.get("draft") else ""
        state = str(pr_data.get("state", "")).lower()
        title = str(pr_data.get("title", ""))
        title_suffix = f"  {title}" if title else ""
        console.print(
            f"  [dim]pr:[/] #{pr_data['number']}{draft_tag}"
            f"  [dim]{state}[/]{title_suffix}"
        )
        # Remove redundant worktree display since it's already shown above
    elif flow.pr_number:
        kv("pr", f"#{flow.pr_number}  [dim](offline)[/]", 1)
    console.print()


def render_flow_created(flow: FlowStatusResponse, task_id: str | None = None) -> None:
    console.print(f"[green]✓[/] Flow created: [cyan]{flow.flow_slug}[/]")
    kv("branch", flow.branch, 1)
    if task_id:
        kv("task", task_id, 1)


def render_flow_status(
    status: FlowStatusResponse,
    issue_titles: dict[int, str] | None = None,
    pr_data: dict[str, Any] | None = None,
    milestone_data: dict[str, Any] | None = None,
    parent_branch: str | None = None,
) -> None:
    """flow show — full detail, YAML style."""
    titles = issue_titles or {}
    status_str = status_text(status.flow_status).plain
    console.print(f"[cyan bold]{status.branch}[/]  [dim](Flow: {status_str})[/]")
    kv("flow_slug", status.flow_slug, 1)
    if parent_branch:
        kv("parent", parent_branch, 1)
    if status.task_issue_number:
        n = status.task_issue_number
        title = titles.get(n, "")
        suffix = f"  [dim]{title}[/]" if title else ""
        console.print(f"  [dim]task_issue:[/] #{n}{suffix}")
    if status.issues:
        related_issues = [i for i in status.issues if i.issue_role == "related"]
        dependency_issues = [i for i in status.issues if i.issue_role == "dependency"]
        for label, items in (
            ("related_issues", related_issues),
            ("dependencies", dependency_issues),
        ):
            if not items:
                continue
            console.print(f"  [dim]{label}:[/]")
            for i in items:
                title = titles.get(i.issue_number, "")
                suffix = f"  [dim]{title}[/]" if title else ""
                console.print(f"    - #{i.issue_number}{suffix}")
    if pr_data:
        draft_tag = " [dim][draft][/]" if pr_data.get("draft") else ""
        state = str(pr_data.get("state", "")).lower()
        console.print(
            f"  [dim]pr:[/] #{pr_data['number']}{draft_tag}"
            f"  [dim]{state}[/]  {pr_data.get('title', '')}"
        )
        worktree = pr_data.get("worktree")
        if worktree:
            kv("worktree", worktree, 2)
        kv("url", pr_data.get("url", ""), 2)
    elif status.pr_number:
        kv("pr", f"#{status.pr_number}  [dim](offline)[/]", 1)
    else:
        console.print(
            "  [dim]pr:[/] [yellow]—[/]  "
            "[dim][hint: run `vibe3 check --fix` to detect][/]"
        )
    for stage, actor, ref in (
        ("plan", status.planner_actor, status.plan_ref),
        ("execute", status.executor_actor, status.report_ref),
        ("review", status.reviewer_actor, status.audit_ref),
    ):
        console.print(f"  [dim]{stage}:[/]")
        kv("actor", actor or "—", 2)
        kv("ref", ref or "—", 2)
    if status.spec_ref:
        kv("spec", status.spec_ref, 1)
    if status.blocked_by:
        kv("blocked_by", status.blocked_by, 1)
    if status.next_step:
        kv("next_step", status.next_step, 1)

    if status.initiated_by:
        kv("initiated_by", status.initiated_by, 1)

    # Always show actor — fallback to worktree identity when flow has no signature
    _actor, _fallback = display_actor(status.latest_actor)
    _suffix = " [dim](worktree)[/]" if _fallback else ""
    actors = [
        f"[dim]latest:[/] {_actor}{_suffix}",
        f"[dim]plan:[/] {status.planner_actor or '—'}",
        f"[dim]run:[/] {status.executor_actor or '—'}",
        f"[dim]review:[/] {status.reviewer_actor or '—'}",
    ]
    console.print(f"  [dim]actor:[/]      {'  '.join(actors)}")

    if milestone_data:
        render_milestone(milestone_data, status.task_issue_number)
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
            kv("started", status.execution_started_at[:19], 2)
        if status.execution_pid:
            kv("pid", status.execution_pid, 2)
    console.print()


def render_flows_status_dashboard(
    flows: list[FlowStatusResponse],
    titles: dict[int, str],
    pr_map: dict[str, dict[str, object]] | None = None,
    worktree_map: dict[str, str] | None = None,
) -> None:
    """flow status dashboard — YAML style with remote title and PR status."""
    pr_map = pr_map or {}
    worktree_map = worktree_map or {}
    for flow in flows:
        task_num = flow.task_issue_number
        title = titles.get(task_num, "—") if task_num else "—"
        worktree = worktree_map.get(flow.branch)
        _render_flow_row(
            flow, title, pr_data=pr_map.get(flow.branch), worktree=worktree
        )


def render_error(message: str) -> None:
    console.print(f"[red]✗[/] {message}")
