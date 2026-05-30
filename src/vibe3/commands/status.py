"""Status command - unified dashboard for flows and orchestra."""

import json
from dataclasses import asdict
from datetime import timezone
from typing import Annotated, cast

import typer

from vibe3.commands.command_options import (
    AllOption,
    FormatOption,
    TraceMinMsOption,
    TraceOption,
)
from vibe3.commands.common import (
    enable_method_trace,
    run_full_check_shortcut,
    validate_trace_options,
)
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.server import _validate_pid_file
from vibe3.services.flow_service import FlowService
from vibe3.services.orchestra_helpers import get_manager_usernames
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
        # Include issues without flow if they are remote (claimed by manager)
        # or in states that should show even without flow
        is_remote = cast(bool, item.get("remote", False))
        if is_remote:
            return True
        return state in {
            IssueState.READY,
            IssueState.HANDOFF,
            IssueState.BLOCKED,
            IssueState.DONE,
            IssueState.CLAIMED,
            IssueState.IN_PROGRESS,
            IssueState.REVIEW,
        }
    return is_auto_task_branch(flow.branch)


def _resolve_server_label(
    config: OrchestraConfig, snapshot_found: bool, server_running: bool
) -> str:
    if snapshot_found and server_running:
        return "[green]running[/]"
    pid, is_valid = _validate_pid_file(config.pid_file)
    if is_valid and pid is not None:
        return "[green]running[/]"
    return "[dim]stopped[/]"


def _compute_effective_server_running(
    snapshot_running: bool, config: OrchestraConfig
) -> bool:
    """Unified server status: snapshot is authoritative, PID-valid is fallback."""
    if snapshot_running:
        return True
    _, pid_valid = _validate_pid_file(config.pid_file)
    return pid_valid


def status(
    all_flows: AllOption = False,
    check: Annotated[
        bool,
        typer.Option("--check", help="显示前先运行完整 vibe3 check"),
    ] = False,
    output_format: FormatOption = "table",
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
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
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    from vibe3.commands.status_render import (
        render_blocked_items,
        render_completed_flows,
        render_epic_items,
        render_issue_progress,
        render_missing_state_items,
        render_pr_ref_items,
        render_remote_items,
        render_rfc_items,
        render_supervisor_issues,
    )

    if json_output and output_format == "table":
        typer.echo(
            "Warning: --json is deprecated, use --format json instead",
            err=True,
        )
        output_format = "json"
    if check:
        run_full_check_shortcut()

    import time

    config = load_orchestra_config()
    orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    if orch_snapshot is None:
        time.sleep(0.5)
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    snapshot_found = orch_snapshot is not None

    if not orch_snapshot:
        _, pid_alive = _validate_pid_file(config.pid_file)
        if pid_alive:
            import time

            time.sleep(0.5)
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

        # Fetch orchestrated issues for JSON/YAML output
        queued_set = set(orch_snapshot.queued_issues)
        query_service = StatusQueryService(repo=config.repo)
        orchestrated_issues = query_service.fetch_orchestrated_issues(
            flows,
            queued_set,
            stale_flows=[],
            manager_usernames=get_manager_usernames(config),
            supervisor_label=config.supervisor_handoff.issue_label,
        )

        output_data = {
            "orchestra": asdict(orch_snapshot),
            "flows": [f.model_dump() for f in flows],
            "orchestrated_issues": orchestrated_issues,
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
        + _resolve_server_label(config, snapshot_found, orch_snapshot.server_running)
    )

    if orch_snapshot.dispatch_blocked:
        console.print(
            "Dispatch: [bold red]FROZEN[/] " f"[dim]({orch_snapshot.blocked_reason})[/]"
        )
        if orch_snapshot.blocked_issue_number is not None:
            console.print(f"  [red]Issue:   #{orch_snapshot.blocked_issue_number}[/]")
        console.print(f"  [red]Reason:  {orch_snapshot.blocked_issue_reason}[/]")
    elif not _compute_effective_server_running(orch_snapshot.server_running, config):
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
        flows.extend(service.list_flows(status="blocked"))

    stale_flows = service.list_flows(status="stale") if not all_flows else []

    queued_set = set(orch_snapshot.queued_issues)
    query_service = StatusQueryService(repo=config.repo)
    orchestrated_issues = query_service.fetch_orchestrated_issues(
        flows,
        queued_set,
        stale_flows=stale_flows,
        manager_usernames=get_manager_usernames(config),
        supervisor_label=config.supervisor_handoff.issue_label,
    )

    supervisor_label = config.supervisor_handoff.issue_label

    # -- Filtering decision tree (see docs/v3/orchestra/task-status-filtering.md) --
    # Rules 0-9: state label is the gate to main flow.
    # No state = never entered main flow; has state = entered main flow.
    # Then branch by assignee (rule 2/3/4) and governed status (rule 5/7/8).

    supervisor_items = [
        item
        for item in orchestrated_issues
        if supervisor_label in cast(list[str], item.get("labels", []))
    ]
    supervisor_numbers = {cast(int, item["number"]) for item in supervisor_items}

    roadmap_rfc_items = [
        item
        for item in orchestrated_issues
        if "roadmap/rfc" in cast(list[str], item.get("labels", []))
        and supervisor_label not in cast(list[str], item.get("labels", []))
    ]
    roadmap_rfc_numbers = {cast(int, item["number"]) for item in roadmap_rfc_items}
    roadmap_epic_items = [
        item
        for item in orchestrated_issues
        if "roadmap/epic" in cast(list[str], item.get("labels", []))
        and supervisor_label not in cast(list[str], item.get("labels", []))
    ]
    roadmap_epic_numbers = {cast(int, item["number"]) for item in roadmap_epic_items}

    # Split missing state items into two categories:
    # 1. Waiting for assignee-pool (no orchestra-governed label) - normal waiting
    # 2. Governed but anomaly (has orchestra-governed label) - needs attention
    manager_usernames = get_manager_usernames(config)

    waiting_for_pool_items = [
        item
        for item in orchestrated_issues
        if item.get("state") is None
        and item.get("assignee") is not None
        and item.get("assignee") in manager_usernames
        and supervisor_label not in cast(list[str], item.get("labels", []))
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
        and "orchestra-governed" not in cast(list[str], item.get("labels", []))
    ]
    governed_anomaly_items = [
        item
        for item in orchestrated_issues
        if item.get("state") is None
        and item.get("assignee") is not None
        and item.get("assignee") in manager_usernames
        and supervisor_label not in cast(list[str], item.get("labels", []))
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
        and "orchestra-governed" in cast(list[str], item.get("labels", []))
    ]
    missing_state_numbers = {
        cast(int, item["number"])
        for item in waiting_for_pool_items + governed_anomaly_items
    }

    task_progress_items = [
        item
        for item in orchestrated_issues
        if _include_issue_in_task_progress(item)
        and cast(int, item["number"]) not in supervisor_numbers
        and cast(int, item["number"]) not in roadmap_rfc_numbers
        and cast(int, item["number"]) not in roadmap_epic_numbers
        and cast(int, item["number"]) not in missing_state_numbers
    ]

    # Separate remote and non-remote items for rendering
    # Exclude BLOCKED from remote_items to prevent double-rendering
    remote_items = [
        item
        for item in task_progress_items
        if cast(bool, item.get("remote"))
        and cast(IssueState, item["state"]) != IssueState.BLOCKED
    ]
    non_remote_items = [
        item for item in task_progress_items if not cast(bool, item.get("remote"))
    ]

    bucketed_items: dict[TaskStatusBucket, list[dict[str, object]]] = {
        TaskStatusBucket.ASSIGNEE_INTAKE: [],
        TaskStatusBucket.READY_QUEUE: [],
        TaskStatusBucket.READY_ANOMALY: [],
        TaskStatusBucket.ACTIVE_ANOMALY: [],
        TaskStatusBucket.OTHER: [],
    }
    for item in non_remote_items:
        state = cast(IssueState | None, item["state"])
        if state == IssueState.DONE:
            continue

        bucket = classify_task_status(
            state,
            cast(str | None, item.get("assignee")),
            get_manager_usernames(config),
        )
        bucketed_items[bucket].append(item)

    render_issue_progress(bucketed_items, config)
    console.print()

    render_remote_items(remote_items)
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
        for item in orchestrated_issues
        if cast(IssueState, item["state"]) == IssueState.BLOCKED
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
        and cast(int, item["number"]) not in supervisor_numbers
    ]

    render_missing_state_items(waiting_for_pool_items, governed_anomaly_items)
    render_rfc_items(roadmap_rfc_items)
    render_epic_items(roadmap_epic_items)
    render_blocked_items(blocked_items)

    if all_flows:
        completed_flows = [
            flow
            for flow in flows
            if getattr(flow, "flow_status", "active") in {"done", "aborted", "merged"}
        ]
        render_completed_flows(completed_flows)
