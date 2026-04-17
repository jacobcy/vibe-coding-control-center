"""Flow UI timeline rendering components."""

from typing import Any

from vibe3.models.flow import FlowEvent, FlowStatusResponse
from vibe3.ui.console import console
from vibe3.ui.flow_ui_primitives import display_actor, kv, status_text

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
    "reviewer_started": "yellow",
    "reviewer_completed": "green",
    "reviewer_aborted": "red",
    "state_transitioned": "cyan bold",
    "state_unchanged": "yellow",
    "blocked": "red bold",
    "failed": "red bold",
    "resumed": "green bold",
    "handoff_plan": "blue",
    "handoff_run": "blue",
    "handoff_review": "magenta",
}


def render_milestone(
    milestone_data: "dict[str, Any]", current_issue: "int | None" = None
) -> None:
    from vibe3.clients.github_issues_ops import parse_blocked_by

    ms_title = milestone_data["title"]
    open_count = int(milestone_data.get("open", 0))
    closed_count = int(milestone_data.get("closed", 0))
    total = open_count + closed_count
    progress = f"{closed_count}/{total} done" if total else "0 issues"
    console.print(f"\n[bold]--- Milestone: {ms_title} [{progress}] ---[/]")
    issues: list[dict[str, Any]] = list(milestone_data.get("issues") or [])
    for item in sorted(issues, key=lambda x: int(x["number"])):
        n = int(item["number"])
        state = str(item.get("state", "open")).upper()
        title = str(item.get("title", ""))
        labels = [lb["name"] for lb in (item.get("labels") or [])]
        is_blocked = "status/blocked" in labels
        is_done = state == "CLOSED"

        if is_done:
            icon = "[green]x[/]"
        elif is_blocked:
            icon = "[red]![/]"
        else:
            icon = "[ ]"

        current = "  [dim]<- this flow[/]" if n == current_issue else ""
        console.print(f"  {icon}  [dim]#{n}[/]  {title}{current}")

        if is_blocked:
            body = str(item.get("body") or "")
            blockers = parse_blocked_by(body)
            if blockers:
                blocker_str = "  ".join(f"#{b}" for b in blockers)
                console.print(f"       [red dim]blocked by: {blocker_str}[/]")


def render_flow_timeline(
    state: FlowStatusResponse,
    events: list[FlowEvent],
    milestone_data: dict[str, Any] | None = None,
    parent_branch: str | None = None,
) -> None:
    status_str = status_text(state.flow_status).plain
    console.print(f"[bold cyan]{state.branch}[/]  [dim](Flow: {status_str})[/]")
    kv("flow_slug", state.flow_slug, 1)
    if parent_branch:
        kv("parent", parent_branch, 1)
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

    # Filter orchestra placeholders from actor fields
    def _filter_orchestra_actor(actor: str | None) -> str | None:
        """Filter out orchestra: placeholder actors."""
        if actor and actor.startswith("orchestra:"):
            return None
        return actor

    filtered_initiated_by = _filter_orchestra_actor(state.initiated_by)
    if filtered_initiated_by:
        kv("initiated_by", filtered_initiated_by, 1)

    # Always show actor — fallback to worktree identity when flow has no signature
    _actor, _fallback = display_actor(state.latest_actor)
    _suffix = " [dim](worktree)[/]" if _fallback else ""
    console.print("  [dim]actor[/]")
    console.print(f"    [dim]latest:[/] {_actor}{_suffix}")

    # Display role actors, filtering orchestra placeholders
    plan_actor = _filter_orchestra_actor(state.planner_actor) or "—"
    run_actor = _filter_orchestra_actor(state.executor_actor) or "—"
    review_actor = _filter_orchestra_actor(state.reviewer_actor) or "—"

    console.print(f"    [dim]plan:[/]    {plan_actor}")
    console.print(f"    [dim]run:[/]     {run_actor}")
    console.print(f"    [dim]review:[/]  {review_actor}")

    # Show blocked/failed reasons if present
    if state.blocked_reason:
        console.print()
        console.print(f"  [red bold]blocked_reason:[/] [red]{state.blocked_reason}[/]")
    if state.failed_reason:
        console.print()
        console.print(f"  [red bold]failed_reason:[/] [red]{state.failed_reason}[/]")

    console.print()

    if not events:
        console.print("[dim]  no events[/]")
        return

    console.print("[bold]--- Timeline ---[/]")
    console.print()

    for event in reversed(events):
        # Skip orchestra placeholder actors - only show actual backend/model
        if event.actor.startswith("orchestra:"):
            continue

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
                    console.print(f"  [dim]- {f}[/]")
            # Priority: log_path > ref for display
            log_path = (
                event.refs.get("log_path") if isinstance(event.refs, dict) else None
            )
            if log_path:
                console.print(f"  [dim]- {log_path}[/]")
            ref = event.refs.get("ref") if isinstance(event.refs, dict) else None
            if ref and not log_path:
                console.print(f"  [dim]- {ref}[/]")
        console.print()

    if milestone_data:
        ms_title = milestone_data["title"]
        open_count = int(milestone_data.get("open", 0))
        closed_count = int(milestone_data.get("closed", 0))
        total = open_count + closed_count
        progress = f"{closed_count}/{total} done" if total else "—"
        console.print(
            f"  [dim]milestone:[/] {ms_title}  [dim][{progress}][/]"
            "  [dim]→ vibe3 flow show --snapshot[/]"
        )

    refs_shown = False
    for label in ["spec_ref", "plan_ref", "report_ref", "audit_ref"]:
        val = getattr(state, label, None)
        if val:
            if not refs_shown:
                console.print("[bold]--- Refs ---[/]")
                refs_shown = True
            actor_field = label.replace("_ref", "_actor")
            actor = getattr(state, actor_field, None) or ""
            actor_str = f"  [dim]{actor}[/]" if actor else ""
            console.print(f"  [dim]{label}[/]  {val}{actor_str}")
    console.print()
