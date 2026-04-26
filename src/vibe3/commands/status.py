"""Status command - unified dashboard for flows and orchestra."""

import json
from typing import Annotated, cast

import typer

from vibe3.commands.common import run_full_check_shortcut, trace_scope
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.server.registry import _validate_pid_file
from vibe3.services.flow_service import FlowService
from vibe3.services.orchestra_status_service import OrchestraStatusService
from vibe3.services.status_query_service import (
    StatusQueryService,
    is_auto_task_branch,
    is_canonical_task_branch,
)
from vibe3.services.task_status_classifier import (
    TaskStatusBucket,
    classify_task_status,
)
from vibe3.ui.console import console

AllOption = Annotated[
    bool, typer.Option("--all", help="显示所有状态的 flow（含 done/aborted/stale）")
]
JsonOption = Annotated[bool, typer.Option("--json", help="JSON 格式输出")]
TraceOption = Annotated[bool, typer.Option("--trace", help="启用调用链路追踪")]


def _include_issue_in_task_progress(item: dict[str, object]) -> bool:
    """Only auto-task flows should participate in task-oriented Issue Progress."""
    flow = cast(FlowStatusResponse | None, item.get("flow"))
    state = cast(IssueState, item["state"])

    if flow is None:
        return state in {
            IssueState.READY,
            IssueState.HANDOFF,
            IssueState.BLOCKED,
            IssueState.FAILED,
            IssueState.DONE,
        }
    return is_auto_task_branch(flow.branch)


def _resolve_server_label(
    config: OrchestraConfig, snapshot_found: bool, server_running: bool
) -> str:
    if snapshot_found and server_running:
        return "[green]running[/]"
    pid, is_valid = _validate_pid_file(config.pid_file)
    if is_valid and pid is not None:
        return "[yellow]unreachable[/]"
    return "[dim]stopped[/]"


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
            "MAJOR": "yellow",
            "BLOCK": "red",
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


def status(
    all_flows: AllOption = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="显示前先运行完整 vibe3 check"),
    ] = False,
    json_output: JsonOption = False,
    trace: TraceOption = False,
) -> None:
    """Show dashboard of all issues and their flow status from Orchestra perspective."""
    with trace_scope(trace, "status", domain="status"):
        if check:
            run_full_check_shortcut()

        # 1. Orchestra State (Issues & Managers)
        config = load_orchestra_config()
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
        snapshot_found = orch_snapshot is not None

        if not orch_snapshot:
            # Fallback if server is not running
            from dataclasses import replace

            from vibe3.execution.flow_dispatch import FlowManager

            orch_service = OrchestraStatusService(
                config, orchestrator=FlowManager(config)
            )
            local_snap = orch_service.snapshot()
            orch_snapshot = replace(local_snap, server_running=False)

        if json_output:
            service = FlowService()
            flows = service.list_flows(status=None if all_flows else "active")

            json_data = {
                "orchestra": (
                    orch_snapshot.model_dump()
                    if hasattr(orch_snapshot, "model_dump")
                    else str(orch_snapshot)
                ),
                "flows": [f.model_dump() for f in flows],
            }
            typer.echo(json.dumps(json_data, indent=2, default=str))
            return

        # Header
        from datetime import datetime

        ts_str = datetime.fromtimestamp(orch_snapshot.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        console.print(f"[bold]Orchestra Status[/] [dim]({ts_str})[/]")
        console.print(
            "Server: "
            + _resolve_server_label(
                config, snapshot_found, orch_snapshot.server_running
            )
        )

        # 1.5 Dispatch blocking (FailedGate)
        if orch_snapshot.dispatch_blocked:
            console.print(
                "Dispatch: [bold red]FROZEN[/] "
                f"[dim]({orch_snapshot.blocked_reason})[/]"
            )
            console.print(f"  [red]Issue:   #{orch_snapshot.blocked_issue_number}[/]")
            console.print(f"  [red]Reason:  {orch_snapshot.blocked_issue_reason}[/]")
        else:
            console.print("Dispatch: [green]active[/]")

        if orch_snapshot.queued_issues:
            console.print(
                f"Queue: [yellow]{len(orch_snapshot.queued_issues)} issues waiting[/]"
            )
        console.print()

        # 2. Issue Tracking (state truth + local scene)
        service = FlowService()
        flows = service.list_flows(status=None if all_flows else "active")
        if not all_flows:
            # Also include done flows to show PRs in the dashboard
            flows.extend(service.list_flows(status="done"))

        stale_flows = service.list_flows(status="stale") if not all_flows else []

        queued_set = set(orch_snapshot.queued_issues)
        query_service = StatusQueryService(repo=config.repo)
        orchestrated_issues = query_service.fetch_orchestrated_issues(
            flows, queued_set, stale_flows=stale_flows
        )
        task_progress_items = [
            item
            for item in orchestrated_issues
            if _include_issue_in_task_progress(item)
        ]
        bucketed_items: dict[TaskStatusBucket, list[dict[str, object]]] = {
            TaskStatusBucket.ASSIGNEE_INTAKE: [],
            TaskStatusBucket.READY_QUEUE: [],
            TaskStatusBucket.READY_ANOMALY: [],
            TaskStatusBucket.OTHER: [],
        }
        for item in task_progress_items:
            # Filter out DONE state from standard progress buckets
            #  to keep them in PR section only
            state = cast(IssueState | None, item["state"])
            if state == IssueState.DONE:
                continue

            bucket = classify_task_status(
                state,
                cast(str | None, item.get("assignee")),
            )
            bucketed_items[bucket].append(item)

        console.print("[bold cyan]Issue Progress:[/]")

        if task_progress_items:
            assignee_items = bucketed_items[TaskStatusBucket.ASSIGNEE_INTAKE]
            ready_items = bucketed_items[TaskStatusBucket.READY_QUEUE]
            ready_anomalies = bucketed_items[TaskStatusBucket.READY_ANOMALY]

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

                    # Queue metadata
                    milestone = cast(str | None, item.get("milestone"))
                    roadmap = cast(str | None, item.get("roadmap"))
                    priority = cast(int, item.get("priority", 0))
                    queue_rank = cast(int | None, item.get("queue_rank"))

                    # Format queue metadata
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
                    console.print(
                        f"  #{number:4}  [cyan]READY     [/]  {display_title}"
                    )
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

                    display_title = title[:48] + "..." if len(title) > 48 else title
                    console.print(f"  #{number:4}  [red]READY     [/]  {display_title}")
                    _render_task_item_details(flow, config)
                    console.print(
                        "             [yellow]missing assignee:[/] "
                        "ready queue historical debt"
                    )
            else:
                console.print("  [dim](none)[/]")
        else:
            console.print("  [dim]No orchestration-tracked issues.[/]")

        console.print()

        # NEW: Show flows with PRs (factually complete, waiting for merge)
        pr_ref_items = [
            item
            for item in task_progress_items
            if item.get("flow") and getattr(item["flow"], "pr_ref", None)
        ]
        console.print("[bold cyan]Flows with PRs (Merge-Ready/Done):[/]")
        if pr_ref_items:
            for item in pr_ref_items:
                number = cast(int, item["number"])
                title = cast(str, item["title"])
                flow = cast(FlowStatusResponse, item["flow"])
                pr_url_value = getattr(flow, "pr_ref", None)
                pr_url: str | None = str(pr_url_value) if pr_url_value else None

                # Show PR URL and state
                state = cast(IssueState, item["state"])
                status_str = state.value.upper()

                display_title = title[:48] + "..." if len(title) > 48 else title
                console.print(f"  #{number:4}  [{status_str:10}]  {display_title}")
                if pr_url:
                    console.print(f"         [cyan]PR: {pr_url}[/]")
        else:
            console.print("  [dim](none)[/]")

        blocked_items = [
            item
            for item in task_progress_items
            if cast(IssueState, item["state"]) == IssueState.BLOCKED
        ]
        console.print("[bold cyan]Blocked Issues:[/]")
        if blocked_items:
            for item in blocked_items:
                number = cast(int, item["number"])
                title = cast(str, item["title"])
                flow = cast(FlowStatusResponse | None, item["flow"])
                blocked_by = cast(tuple[int, ...] | None, item.get("blocked_by"))
                blocked_reason = cast(str | None, item.get("blocked_reason"))

                if flow is None:
                    flow_info = "[dim](no flow scene)[/]"
                elif getattr(flow, "flow_status", "active") == "stale":
                    flow_info = f"[dim]{flow.branch} (stale)[/]"
                else:
                    flow_info = f"[cyan]{flow.branch}[/]"

                console.print(f"  #{number:4}  {title[:56]}...  [dim]{flow_info}[/]")
                if blocked_by:
                    blocked_by_str = ", ".join(f"#{n}" for n in blocked_by)
                    console.print(f"         [yellow]blocked by:[/] {blocked_by_str}")
                if blocked_reason:
                    console.print(f"         [yellow]reason:[/] {blocked_reason}")
        else:
            console.print("  [dim](none)[/]")

        failed_items = [
            item
            for item in task_progress_items
            if cast(IssueState, item["state"]) == IssueState.FAILED
        ]
        console.print("\n[bold cyan]Failed Issues:[/]")
        if failed_items:
            for item in failed_items:
                number = cast(int, item["number"])
                title = cast(str, item["title"])
                flow = cast(FlowStatusResponse | None, item["flow"])
                reason = cast(str | None, item.get("failed_reason"))
                if flow is None:
                    flow_info = "[dim](no flow scene)[/]"
                elif getattr(flow, "flow_status", "active") == "stale":
                    flow_info = f"[dim]{flow.branch} (stale)[/]"
                else:
                    flow_info = f"[cyan]{flow.branch}[/]"
                console.print(f"  #{number:4}  {title[:56]}...  [dim]{flow_info}[/]")
                if reason:
                    console.print(f"         [red]reason:[/] {reason}")
        else:
            console.print("  [dim](none)[/]")

        # NEW: Show completed/aborted flows (no longer active)
        if all_flows:
            completed_flows = [
                flow
                for flow in flows
                if getattr(flow, "flow_status", "active")
                in {"done", "aborted", "merged"}
            ]
            console.print("\n[bold cyan]Completed/Aborted Flows:[/]")
            if completed_flows:
                for flow in completed_flows:
                    task = (
                        f"#{flow.task_issue_number}"
                        if flow.task_issue_number
                        else "(no task)"
                    )
                    flow_status = getattr(flow, "flow_status", "active")
                    console.print(
                        f"  [cyan]{flow.branch:30}[/] "
                        f"[dim]task:[/] {task:10} "
                        f"[dim]status:[/] {flow_status}"
                    )
            else:
                console.print("  [dim](none)[/]")

        # 3. Local scene context (tracked flows + worktrees)
        worktree_map = query_service.fetch_worktree_map()

        if flows:
            auto_flows = [
                flow
                for flow in flows
                if is_auto_task_branch(flow.branch) and flow.branch in worktree_map
            ]
            manual_flows = [
                flow for flow in flows if not is_auto_task_branch(flow.branch)
            ]

            console.print("\n[bold cyan]Auto Task Scenes:[/]")
            if auto_flows:
                for flow in auto_flows:
                    wt = worktree_map.get(flow.branch, "(no worktree)")
                    if is_canonical_task_branch(flow.branch, flow.task_issue_number):
                        console.print(f"  [cyan]{flow.branch:30}[/] [dim]wt:[/] {wt}")
                    else:
                        task = (
                            f"#{flow.task_issue_number}"
                            if flow.task_issue_number
                            else "(no task)"
                        )
                        console.print(
                            f"  [cyan]{flow.branch:30}[/] "
                            f"[dim]wt:[/] {wt:15} [dim]task:[/] {task}"
                        )

            else:
                console.print("  [dim](none)[/]")

            console.print("\n[bold cyan]Manual Scenes:[/]")
            if manual_flows:
                for flow in manual_flows:
                    wt = worktree_map.get(flow.branch, "(no worktree)")
                    task = (
                        f"#{flow.task_issue_number}"
                        if flow.task_issue_number
                        else "(no task)"
                    )
                    console.print(
                        f"  [cyan]{flow.branch:30}[/] "
                        f"[dim]wt:[/] {wt:15} [dim]task:[/] {task}"
                    )
            else:
                console.print("  [dim](none)[/]")
