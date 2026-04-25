"""Flow UI rendering."""

from typing import Any

from vibe3.models.flow import FlowStatusResponse
from vibe3.ui.console import console
from vibe3.ui.flow_ui_primitives import display_actor, kv, resolve_ref_path, status_text
from vibe3.ui.flow_ui_timeline import (  # noqa: F401
    render_flow_timeline,
    render_milestone,
)
from vibe3.utils.path_helpers import ref_to_handoff_cmd


def _render_flow_row(
    flow: FlowStatusResponse,
    title: str | None = None,
    pr_data: dict[str, object] | None = None,
    worktree: str | None = None,
) -> None:
    """Render flow row in task-status style.

    Compact format:
    - With worktree: Show issue#, title, PR, worktree on separate lines
    - Without worktree: Show only branch and issue# (minimal)
    """
    has_worktree = bool(worktree)

    # Line 1: Branch and state
    status_str = status_text(flow.flow_status).plain
    console.print(f"  [cyan]{flow.branch}[/]  [dim]({status_str})[/]")

    # Line 2: Issue and title
    if flow.task_issue_number:
        issue_str = f"#{flow.task_issue_number}"
        title_str = f"  {title}" if title else ""
        console.print(f"    [dim]issue:[/] {issue_str}{title_str}")

    # Line 3: PR (if exists)
    if pr_data:
        draft_tag = " [dim][draft][/]" if pr_data.get("draft") else ""
        state = str(pr_data.get("state", "")).lower()
        pr_title = str(pr_data.get("title", ""))
        title_suffix = f"  {pr_title}" if pr_title else ""
        console.print(
            f"    [dim]PR:[/] #{pr_data['number']}{draft_tag}"
            f"  [dim]{state}[/]{title_suffix}"
        )
    elif flow.pr_number:
        console.print(f"    [dim]PR:[/] #{flow.pr_number}  [dim](offline)[/]")

    # Line 4: Worktree (if exists)
    if has_worktree:
        console.print(f"    [dim]worktree:[/] {worktree}")

    # Add verdict for active flows with worktree
    if has_worktree and flow.latest_verdict:
        v = flow.latest_verdict
        color = {
            "PASS": "green",
            "MAJOR": "yellow",
            "BLOCK": "red",
        }.get(v.verdict, "cyan")
        console.print(
            f"    [dim]verdict:[/] [{color}]{v.verdict}[/] [dim]({v.actor})[/]"
        )

    console.print()  # Empty line between flows


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
    worktree_root: str | None = None,
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
        if ref:
            ref_display = resolve_ref_path(ref, worktree_root)
            ref_cmd = ref_to_handoff_cmd(ref_display, status.branch)
        else:
            ref_cmd = "—"
        console.print(f"  [dim]{stage}:[/]")
        kv("actor", actor or "—", 2)
        kv("ref", ref_cmd, 2)
    # Latest verdict — shown inline under review results
    if status.latest_verdict:
        v = status.latest_verdict
        verdict_color = {"PASS": "green", "MAJOR": "yellow", "BLOCK": "red"}.get(
            v.verdict, "cyan"
        )
        console.print(
            f"  [dim]verdict:[/] [{verdict_color}]{v.verdict}[/]" f"  [dim]{v.actor}[/]"
        )

    from vibe3.services.spec_ref_service import SpecRefService

    spec_service = SpecRefService()
    spec_display = spec_service.get_spec_display(
        status.spec_ref, status.task_issue_number
    )
    kv("spec", spec_display, 1)
    if status.blocked_by:
        kv("blocked_by", status.blocked_by, 1)
    if status.next_step:
        kv("next_step", status.next_step, 1)

    if status.initiated_by:
        kv("initiated_by", status.initiated_by, 1)

    # Always show actor — fallback to worktree identity when flow has no signature
    _actor, _fallback = display_actor(status.latest_actor)
    _suffix = " [dim](worktree)[/]" if _fallback else ""

    # Display actors on separate lines for better readability
    console.print("  [dim]actor[/]")
    console.print(f"    [dim]latest:[/] {_actor}{_suffix}")
    console.print(f"    [dim]plan:[/] {status.planner_actor or '—'}")
    console.print(f"    [dim]run:[/] {status.executor_actor or '—'}")
    console.print(f"    [dim]review:[/] {status.reviewer_actor or '—'}")

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
    """Flow status dashboard — classified by branch type and state.

    Classifies flows into categories:
    1. Auto Tasks: task/issue-N or dev/issue-N branches (automated)
    2. Issue Bound: Manual branches with issue binding
    3. Manual: Manual branches without issue binding

    Groups by state within each category:
    - Active: Normal active flows
    - Blocked: Flows with blocked_by
    - Done/Aborted/Stale: Completed flows
    """
    from vibe3.services.flow_classifier import (
        FlowCategory,
        FlowState,
        classify_flow,
        get_flow_state,
    )

    pr_map = pr_map or {}
    worktree_map = worktree_map or {}

    # Classify and group flows
    categorized: dict[FlowCategory, dict[FlowState, list[FlowStatusResponse]]] = {
        FlowCategory.AUTO_TASK: {},
        FlowCategory.ISSUE_BOUND: {},
        FlowCategory.MANUAL: {},
    }

    for flow in flows:
        category = classify_flow(flow)
        state = get_flow_state(flow)

        if state not in categorized[category]:
            categorized[category][state] = []

        categorized[category][state].append(flow)

    # Render by category
    def render_category(
        category: FlowCategory,
        label: str,
        state_flows: dict[FlowState, list[FlowStatusResponse]],
    ) -> None:
        """Render a category with state grouping."""
        if not state_flows:
            return

        console.print(f"\n[bold]{label}[/]")

        # Order states for display
        state_order = [
            FlowState.ACTIVE,
            FlowState.BLOCKED,
            FlowState.DONE,
            FlowState.STALE,
            FlowState.ABORTED,
        ]

        for state in state_order:
            flows_in_state = state_flows.get(state, [])
            if not flows_in_state:
                continue

            # State header (only if non-active or multiple states)
            if state != FlowState.ACTIVE or len(state_flows) > 1:
                state_label = state.value.upper()
                console.print(f"  [dim]{state_label}:[/]")

            # Render flows in this state
            for flow in flows_in_state:
                task_num = flow.task_issue_number
                title = titles.get(task_num, "—") if task_num else "—"
                worktree = worktree_map.get(flow.branch)
                _render_flow_row(
                    flow, title, pr_data=pr_map.get(flow.branch), worktree=worktree
                )

    # Render categories in order
    render_category(
        FlowCategory.AUTO_TASK,
        "Active Tasks (automated)",
        categorized[FlowCategory.AUTO_TASK],
    )
    render_category(
        FlowCategory.ISSUE_BOUND,
        "Issue-Bound Branches",
        categorized[FlowCategory.ISSUE_BOUND],
    )
    render_category(
        FlowCategory.MANUAL, "Manual Branches", categorized[FlowCategory.MANUAL]
    )


def render_error(message: str) -> None:
    console.print(f"[red]✗[/] {message}")
