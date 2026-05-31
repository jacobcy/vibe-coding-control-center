"""Status dashboard UI rendering functions.

Filtering rules: docs/v3/orchestra/task-status-filtering.md
"""

from typing import cast

from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.services.task_status_classifier import TaskStatusBucket
from vibe3.ui.console import console
from vibe3.utils.error_message_cleaner import (
    CODEAGENT_WRAPPER_ANYWHERE_RE,
    clean_error_message,
)


def _extract_blocked_reason_summary(blocked_reason: str) -> str:
    """Extract key information from blocked_reason for status display.

    Filters out verbose runtime details (TMPDIR, Recent Errors, stdin mode).
    Preserves short status messages and error codes for quick diagnosis.
    """
    if not blocked_reason:
        return ""

    lines = blocked_reason.strip().split("\n")
    if not lines:
        return ""

    # First, remove the "codeagent-wrapper failed (code X):" prefix
    # Use ANYWHERE version to handle "E_EXEC_NO_OUTPUT: codeagent-wrapper..."
    first_line = CODEAGENT_WRAPPER_ANYWHERE_RE.sub("", lines[0].strip())

    # If first line becomes empty or only contains error code
    # (e.g., "E_EXEC_NO_OUTPUT:"), try next line for more descriptive error
    if (not first_line or first_line.rstrip(":").startswith("E_")) and len(lines) > 1:
        next_line = lines[1].strip()
        if next_line:
            first_line = next_line

    if len(first_line) <= 60 and "CLAUDE_CODE_TMPDIR" not in first_line:
        result = first_line
    else:
        cleaned = clean_error_message(first_line)

        if len(cleaned) <= 80:
            result = cleaned
        else:
            # Try to find a sentence boundary
            for sep in ["。", "."]:
                pos = cleaned.rfind(sep, 0, 80)
                if pos > 0:
                    result = cleaned[: pos + 1]
                    break
            else:
                # No sentence boundary found, just truncate
                result = cleaned[:80]

    # Don't end with colon - it looks awkward in "reason: xxx:" format
    if result.endswith(":"):
        result = result[:-1]

    return result


def _render_task_item_details(
    flow: FlowStatusResponse | None,
    config: OrchestraConfig,
    assignee: str | None = None,
) -> None:
    """Render shared task detail lines for task-oriented dashboard sections."""
    flow_info = (
        f"[dim]flow:[/] [cyan]{flow.branch}[/]"
        if flow
        else "[dim]flow:[/] [dim](none)[/]"
    )
    detail_parts = [flow_info]
    if assignee:
        detail_parts.append(f"[dim]assignee:[/] [cyan]{assignee}[/]")
    console.print("             " + "  ".join(detail_parts))

    if not flow:
        return

    if flow.plan_ref:
        console.print(f"             [dim]plan:[/] [cyan]{flow.plan_ref}[/]")
    if flow.report_ref:
        console.print(f"             [dim]report:[/] [cyan]{flow.report_ref}[/]")
    if flow.latest_verdict:
        v = flow.latest_verdict
        color = {
            "PASS": "green",
            "MINOR": "cyan",
            "MAJOR": "yellow",
            "BLOCK": "red",
            "REFUSE": "magenta",
        }.get(v.verdict, "cyan")
        console.print(
            f"             [dim]verdict:[/] "
            f"[{color}]{v.verdict}[/] [dim]({v.actor})[/]"
        )
    if flow.pr_number:
        pr_ref = (
            f"https://github.com/{config.repo}/pull/{flow.pr_number}"
            if config.repo
            else f"PR #{flow.pr_number}"
        )
        console.print(f"             [dim]PR:[/] [cyan]{pr_ref}[/]")


def render_issue_progress(
    bucketed_items: dict[TaskStatusBucket, list[dict[str, object]]],
    config: OrchestraConfig,
) -> None:
    """Render Issue Progress section (Assignee Intake, Ready Queue, Exceptions)."""
    assignee_items = bucketed_items[TaskStatusBucket.ASSIGNEE_INTAKE]
    ready_items = bucketed_items[TaskStatusBucket.READY_QUEUE]
    ready_anomalies = bucketed_items[TaskStatusBucket.READY_ANOMALY]
    active_anomalies = bucketed_items[TaskStatusBucket.ACTIVE_ANOMALY]

    console.print("[bold cyan]Issue Progress:[/]")
    console.print("  [bold]Assignee Intake:[/]")
    if assignee_items:
        for item in assignee_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            state = cast(IssueState, item["state"])
            flow = cast(FlowStatusResponse | None, item["flow"])
            is_queued = cast(bool, item["queued"])
            assignee = cast(str | None, item.get("assignee"))

            status_str = "QUEUED" if is_queued else state.value.upper()
            status_color = "yellow" if is_queued else "green"
            console.print(
                f"  #{number:4}  [{status_color}]{status_str:10}[/]"
                f"  {title[:48] + ('...' if len(title) > 48 else '')}"
            )
            _render_task_item_details(flow, config, assignee=assignee)
    else:
        console.print("  [dim](none)[/]")

    console.print("\n  [bold]Ready Queue:[/]")
    if ready_items:
        for item in ready_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            flow = cast(FlowStatusResponse | None, item["flow"])
            assignee = cast(str | None, item.get("assignee"))

            milestone = cast(str | None, item.get("milestone"))
            roadmap = cast(str | None, item.get("roadmap"))
            priority = cast(int, item.get("priority", 0))
            queue_rank = cast(int | None, item.get("queue_rank"))

            metadata_parts: list[str] = []
            if queue_rank is not None:
                metadata_parts.append(f"rank={queue_rank}")
            if milestone:
                metadata_parts.append(f"milestone={milestone}")
            if roadmap:
                metadata_parts.append(f"roadmap/{roadmap}")
            metadata_parts.append(f"priority/{priority}")
            metadata_str = "  ".join(metadata_parts)

            display_title = title[:48] + "..." if len(title) > 48 else title
            console.print(f"  #{number:4}  [cyan]READY     [/]  {display_title}")
            _render_task_item_details(flow, config, assignee=assignee)
            console.print(f"             [dim]{metadata_str}[/]")
    else:
        console.print("  [dim](none)[/]")

    console.print("\n  [bold]Ready Exceptions:[/]")
    if ready_anomalies:
        for item in ready_anomalies:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            flow = cast(FlowStatusResponse | None, item["flow"])
            assignee = cast(str | None, item.get("assignee"))

            display_title = title[:48] + "..." if len(title) > 48 else title
            console.print(f"  #{number:4}  [red]READY     [/]  {display_title}")
            _render_task_item_details(flow, config, assignee=assignee)
            if assignee:
                console.print(
                    "             [yellow]non-manager assignee:[/] "
                    "requires assignee-pool or roadmap intake repair"
                )
            else:
                console.print(
                    "             [yellow]missing assignee:[/] "
                    "ready queue historical debt"
                )
    else:
        console.print("  [dim](none)[/]")

    console.print("\n  [bold]Active Exceptions:[/]")
    if active_anomalies:
        for item in active_anomalies:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            state = cast(IssueState, item["state"])
            flow = cast(FlowStatusResponse | None, item["flow"])

            state_str = state.value.upper()
            display_title = title[:48] + "..." if len(title) > 48 else title
            console.print(f"  #{number:4}  [red]{state_str:10}[/]  {display_title}")
            _render_task_item_details(flow, config)
            console.print(
                "             [yellow]missing assignee:[/] active state"
                " but no assignee (rule 2)"
            )
    else:
        console.print("  [dim](none)[/]")


def render_remote_items(remote_items: list[dict[str, object]]) -> None:
    """Render Remote Tasks (no local flow) section."""
    console.print("[bold cyan]Remote Tasks (no local flow):[/]")
    if remote_items:
        for item in remote_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            state = cast(IssueState, item["state"])
            assignee = cast(str | None, item.get("assignee"))
            display_title = title[:48] + "..." if len(title) > 48 else title
            state_str = state.value.upper()
            assignee_str = f" [dim]({assignee})[/]" if assignee else ""
            remote_marker = "[dim][remote][/]"
            console.print(
                f"  #{number:4}  [yellow]{state_str:10}[/]  "
                f"{remote_marker}{assignee_str} {display_title}"
            )
    else:
        console.print("  [dim](none)[/]")


def render_supervisor_issues(supervisor_items: list[dict[str, object]]) -> None:
    """Render Supervisor Issues section."""
    console.print("[bold cyan]Supervisor Issues:[/]")
    if supervisor_items:
        for item in supervisor_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            state = cast(IssueState | None, item["state"])
            display_title = title[:52] + "..." if len(title) > 52 else title
            state_str = state.value.upper() if state else "NO STATE"
            console.print(f"  #{number:4}  [{state_str}]  {display_title}")
    else:
        console.print("  [dim](none)[/]")


def render_pr_ref_items(pr_ref_items: list[dict[str, object]]) -> None:
    """Render Flows with PRs section."""
    console.print("[bold cyan]Flows with PRs (Merge-Ready/Done):[/]")
    if pr_ref_items:
        for item in pr_ref_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            flow = cast(FlowStatusResponse, item["flow"])
            pr_url_value = getattr(flow, "pr_ref", None)
            pr_url: str | None = str(pr_url_value) if pr_url_value else None

            state = cast(IssueState, item["state"])
            status_str = state.value.upper()

            display_title = title[:48] + "..." if len(title) > 48 else title
            console.print(f"  #{number:4}  [cyan]{status_str:10}[/]  {display_title}")
            if pr_url:
                console.print(f"         [cyan]PR: {pr_url}[/]")
    else:
        console.print("  [dim](none)[/]")


def render_blocked_items(blocked_items: list[dict[str, object]]) -> None:
    """Render Blocked Issues section."""
    console.print("\n[bold cyan]Blocked Issues:[/]")
    if blocked_items:
        for item in blocked_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            flow = cast(FlowStatusResponse | None, item["flow"])
            blocked_by = cast(tuple[int, ...] | None, item.get("blocked_by"))
            blocked_reason = cast(str | None, item.get("blocked_reason"))

            display_title = title[:60] + ("..." if len(title) > 60 else "")
            console.print(f"  #{number:4}  [red]BLOCKED[/]  {display_title}")

            if flow:
                console.print(f"         [dim]flow:[/] [cyan]{flow.branch}[/]")
            else:
                console.print(
                    "         [dim]flow:[/] [dim](no flow scene)[/] [cyan]\\[remote][/]"
                )

            if blocked_by:
                blocked_by_str = ", ".join(f"#{n}" for n in blocked_by)
                console.print(f"         [yellow]blocked by:[/] {blocked_by_str}")

            if blocked_reason:
                reason_summary = _extract_blocked_reason_summary(blocked_reason)
                console.print(f"         [yellow]reason:[/] {reason_summary}")
    else:
        console.print("  [dim](none)[/]")


def render_rfc_items(rfc_items: list[dict[str, object]]) -> None:
    """Render Roadmap RFC section (issues needing human design input)."""
    console.print("\n[bold cyan]Roadmap RFC:[/]")
    if rfc_items:
        for item in rfc_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            state = cast(IssueState | None, item["state"])
            flow = cast(FlowStatusResponse | None, item["flow"])

            state_str = state.value.upper() if state else "NO STATE"
            display_title = title[:60] + ("..." if len(title) > 60 else "")
            console.print(f"  #{number:4}  [yellow]{state_str:10}[/]  {display_title}")

            if flow:
                console.print(f"         [dim]flow:[/] [cyan]{flow.branch}[/]")
    else:
        console.print("  [dim](none)[/]")


def render_epic_items(epic_items: list[dict[str, object]]) -> None:
    """Render Roadmap Epic section (parent governance containers)."""
    console.print("\n[bold cyan]Roadmap Epic:[/]")
    if epic_items:
        for item in epic_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            state = cast(IssueState | None, item["state"])
            flow = cast(FlowStatusResponse | None, item["flow"])

            state_str = state.value.upper() if state else "NO STATE"
            display_title = title[:60] + ("..." if len(title) > 60 else "")
            console.print(f"  #{number:4}  [magenta]{state_str:10}[/]  {display_title}")

            if flow:
                console.print(f"         [dim]flow:[/] [cyan]{flow.branch}[/]")
    else:
        console.print("  [dim](none)[/]")


def render_completed_flows(completed_flows: list[FlowStatusResponse]) -> None:
    """Render Completed/Aborted Flows section."""
    console.print("\n[bold cyan]Completed/Aborted Flows:[/]")
    if completed_flows:
        for flow in completed_flows:
            task = (
                f"#{flow.task_issue_number}" if flow.task_issue_number else "(no task)"
            )
            flow_status = getattr(flow, "flow_status", "active")
            console.print(
                f"  [cyan]{flow.branch:30}[/] "
                f"[dim]task:[/] {task:10} "
                f"[dim]status:[/] {flow_status}"
            )
    else:
        console.print("  [dim](none)[/]")


def render_missing_state_items(
    waiting_for_pool_items: list[dict[str, object]],
    governed_anomaly_items: list[dict[str, object]],
) -> None:
    """Render issues that are relevant to the dashboard but have no state label.

    Splits into two categories:
    1. Waiting for Assignee Pool: Issues with manager assignee
       but no orchestra-governed label
    2. Governed but Anomaly: Issues with orchestra-governed label
       but still missing state
    """
    # Render waiting for assignee pool (normal)
    console.print("\n[bold cyan]Missing State Label - Waiting for Assignee Pool:[/]")
    if waiting_for_pool_items:
        for item in waiting_for_pool_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            assignee = cast(str | None, item.get("assignee"))
            display_title = title[:60] + ("..." if len(title) > 60 else "")
            assignee_str = f" [dim]({assignee})[/]" if assignee else ""
            console.print(
                f"  #{number:4}  [yellow]NO STATE  [/]  {display_title}{assignee_str}"
            )
    else:
        console.print("  [dim](none)[/]")

    # Render governed but anomaly (needs attention)
    console.print("\n[bold cyan]Missing State Label - Governed but Anomaly:[/]")
    if governed_anomaly_items:
        for item in governed_anomaly_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            assignee = cast(str | None, item.get("assignee"))
            display_title = title[:60] + ("..." if len(title) > 60 else "")
            assignee_str = f" [dim]({assignee})[/]" if assignee else ""
            console.print(
                f"  #{number:4}  [red]NO STATE  [/]  {display_title}{assignee_str}"
            )
            console.print(
                "         [yellow]⚠️  orchestra-governed label present"
                " but state missing[/]"
            )
    else:
        console.print("  [dim](none)[/]")


def render_scene_sections(
    flows: list[FlowStatusResponse],
    worktree_map: dict[str, str],
) -> None:
    """Render active flow scenes."""
    active_flows = [
        flow
        for flow in flows
        if getattr(flow, "flow_status", "active") not in {"done", "aborted", "merged"}
    ]

    console.print("\n[bold cyan]Active Scenes:[/]")
    if active_flows:
        for flow in active_flows:
            wt = worktree_map.get(flow.branch, "(no worktree)")
            task = (
                f"#{flow.task_issue_number}" if flow.task_issue_number else "(no task)"
            )
            console.print(
                f"  [cyan]{flow.branch:30}[/] "
                f"[dim]wt:[/] {wt:15} [dim]task:[/] {task}"
            )
    else:
        console.print("  [dim](none)[/]")
