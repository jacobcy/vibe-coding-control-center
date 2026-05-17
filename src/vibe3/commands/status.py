"""Status command - unified dashboard for flows and orchestra."""

import json
from datetime import timezone
from typing import Annotated, cast

import typer

from vibe3.commands.command_options import (
    AllOption,
    FormatOption,
    TraceOption,
)
from vibe3.commands.common import run_full_check_shortcut, trace_scope
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.server.registry import _validate_pid_file
from vibe3.services.flow_service import FlowService
from vibe3.services.orchestra_status_service import OrchestraStatusService
from vibe3.services.status_query_service import StatusQueryService, is_auto_task_branch
from vibe3.services.task_status_classifier import (
    TaskStatusBucket,
    classify_task_status,
)
from vibe3.ui.console import console
from vibe3.utils.time_format import format_age_aware_time


def _include_issue_in_task_progress(item: dict[str, object]) -> bool:
    """Only auto-task flows should participate in task-oriented Issue Progress."""
    flow = cast(FlowStatusResponse | None, item.get("flow"))
    state = cast(IssueState, item["state"])

    if flow is None:
        return state in {
            IssueState.READY,
            IssueState.HANDOFF,
            IssueState.BLOCKED,
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


def status(
    all_flows: AllOption = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="显示前先运行完整 vibe3 check"),
    ] = False,
    output_format: FormatOption = "table",
    trace: TraceOption = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="[DEPRECATED] Use --format json instead",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Show dashboard of all issues and their flow status from Orchestra perspective."""
    from vibe3.commands.status_render import (
        render_blocked_items,
        render_completed_flows,
        render_issue_progress,
        render_pr_ref_items,
        render_scene_sections,
        render_supervisor_issues,
    )

    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"
    with trace_scope(trace, "status", domain="status"):
        if check:
            run_full_check_shortcut()

        config = load_orchestra_config()
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
        snapshot_found = orch_snapshot is not None

        if not orch_snapshot:
            from dataclasses import replace

            from vibe3.services.flow_orchestrator_service import (
                FlowOrchestratorService,
            )

            orch_service = OrchestraStatusService(
                config, orchestrator=FlowOrchestratorService(config)
            )
            local_snap = orch_service.snapshot()
            orch_snapshot = replace(local_snap, server_running=False)

        if output_format in ("json", "yaml"):
            service = FlowService()
            flows = service.list_flows(status=None if all_flows else "active")

            output_data = {
                "orchestra": (
                    orch_snapshot.model_dump()
                    if hasattr(orch_snapshot, "model_dump")
                    else str(orch_snapshot)
                ),
                "flows": [f.model_dump() for f in flows],
            }

            if output_format == "json":
                typer.echo(json.dumps(output_data, indent=2, default=str))
            else:  # yaml
                import yaml

                typer.echo(
                    yaml.dump(output_data, default_flow_style=False, allow_unicode=True)
                )
            return

        from datetime import datetime

        ts_utc = datetime.fromtimestamp(orch_snapshot.timestamp, tz=timezone.utc)
        ts_str = format_age_aware_time(ts_utc)
        console.print(f"[bold]Orchestra Status[/] [dim]({ts_str})[/]")
        console.print(
            "Server: "
            + _resolve_server_label(
                config, snapshot_found, orch_snapshot.server_running
            )
        )

        if orch_snapshot.dispatch_blocked:
            console.print(
                "Dispatch: [bold red]FROZEN[/] "
                f"[dim]({orch_snapshot.blocked_reason})[/]"
            )
            console.print(f"  [red]Issue:   #{orch_snapshot.blocked_issue_number}[/]")
            console.print(f"  [red]Reason:  {orch_snapshot.blocked_issue_reason}[/]")
        elif not orch_snapshot.server_running:
            console.print("Dispatch: [dim]inactive (server stopped)[/]")
        else:
            console.print("Dispatch: [green]active[/]")

        if orch_snapshot.queued_issues:
            console.print(
                f"Queue: [yellow]{len(orch_snapshot.queued_issues)} issues waiting[/]"
            )
        console.print()

        service = FlowService()
        flows = service.list_flows(status=None if all_flows else "active")
        if not all_flows:
            flows.extend(service.list_flows(status="done"))

        stale_flows = service.list_flows(status="stale") if not all_flows else []

        queued_set = set(orch_snapshot.queued_issues)
        query_service = StatusQueryService(repo=config.repo)
        orchestrated_issues = query_service.fetch_orchestrated_issues(
            flows, queued_set, stale_flows=stale_flows
        )

        supervisor_label = config.supervisor_handoff.issue_label
        supervisor_items = [
            item
            for item in orchestrated_issues
            if supervisor_label in cast(list[str], item.get("labels", []))
        ]
        supervisor_numbers = {cast(int, item["number"]) for item in supervisor_items}

        task_progress_items = [
            item
            for item in orchestrated_issues
            if _include_issue_in_task_progress(item)
            and cast(int, item["number"]) not in supervisor_numbers
        ]
        bucketed_items: dict[TaskStatusBucket, list[dict[str, object]]] = {
            TaskStatusBucket.ASSIGNEE_INTAKE: [],
            TaskStatusBucket.READY_QUEUE: [],
            TaskStatusBucket.READY_ANOMALY: [],
            TaskStatusBucket.OTHER: [],
        }
        for item in task_progress_items:
            state = cast(IssueState | None, item["state"])
            if state == IssueState.DONE:
                continue

            bucket = classify_task_status(
                state,
                cast(str | None, item.get("assignee")),
                config.get_manager_usernames(),
            )
            bucketed_items[bucket].append(item)

        render_issue_progress(bucketed_items, config)
        console.print()

        render_supervisor_issues(supervisor_items)
        console.print()

        pr_ref_items = [
            item
            for item in task_progress_items
            if item.get("flow") and getattr(item["flow"], "pr_ref", None)
        ]
        render_pr_ref_items(pr_ref_items)

        blocked_items = [
            item
            for item in task_progress_items
            if cast(IssueState, item["state"]) == IssueState.BLOCKED
        ]
        render_blocked_items(blocked_items)

        if all_flows:
            completed_flows = [
                flow
                for flow in flows
                if getattr(flow, "flow_status", "active")
                in {"done", "aborted", "merged"}
            ]
            render_completed_flows(completed_flows)

        worktree_map = query_service.fetch_worktree_map()

        if flows:
            render_scene_sections(flows, worktree_map)
