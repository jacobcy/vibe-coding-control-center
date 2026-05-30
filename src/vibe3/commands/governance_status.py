"""Governance status command - focused view for governance tracking."""

import json
from typing import Annotated, cast

import typer

from vibe3.commands.command_options import TraceMinMsOption, TraceOption
from vibe3.commands.common import enable_method_trace, validate_trace_options
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_service import FlowService
from vibe3.services.orchestra_helpers import get_manager_usernames
from vibe3.services.orchestra_status_service import OrchestraStatusService
from vibe3.services.status_query_service import StatusQueryService
from vibe3.ui.console import console


def render_governance_dashboard(
    manager_assigned: list[dict[str, object]],
    rfc_items: list[dict[str, object]],
    epic_items: list[dict[str, object]],
    blocked_items: list[dict[str, object]],
    waiting_pool: list[dict[str, object]],
    governed_anomaly: list[dict[str, object]],
) -> None:
    """Render governance-focused status dashboard.

    Consolidates governance-relevant issue subsets into a compact single-view summary.
    """
    console.print("[bold]Governance Status[/]\n")

    # Manager-Assigned Issues section
    console.print(f"[bold cyan]Manager-Assigned Issues:[/] {len(manager_assigned)}")
    if manager_assigned:
        # Group by state label
        by_state: dict[str, list[dict[str, object]]] = {}
        for item in manager_assigned:
            state = cast(IssueState | None, item.get("state"))
            state_str = state.value if state else "no-state"
            if state_str not in by_state:
                by_state[state_str] = []
            by_state[state_str].append(item)

        for state_str in sorted(by_state.keys()):
            items = by_state[state_str]
            for item in items:
                number = cast(int, item["number"])
                title = cast(str, item["title"])
                state = cast(IssueState | None, item.get("state"))
                state_str_display = state.value if state else "no-state"
                display_title = title[:48] + "..." if len(title) > 48 else title
                console.print(
                    f"  #{number:4}  [cyan]{state_str_display:12}[/]  {display_title}"
                )
    else:
        console.print("  [dim](none)[/]")
    console.print()

    # RFC Issues section
    console.print(f"[bold cyan]RFC Issues:[/] {len(rfc_items)}")
    if rfc_items:
        for item in rfc_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            state = cast(IssueState | None, item.get("state"))
            state_str = state.value if state else "no-state"
            display_title = title[:60] + "..." if len(title) > 60 else title
            console.print(f"  #{number:4}  [yellow]{state_str:10}[/]  {display_title}")
    else:
        console.print("  [dim](none)[/]")
    console.print()

    # Epic Issues section
    console.print(f"[bold cyan]Epic Issues:[/] {len(epic_items)}")
    if epic_items:
        for item in epic_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            state = cast(IssueState | None, item.get("state"))
            state_str = state.value if state else "no-state"
            display_title = title[:60] + "..." if len(title) > 60 else title
            console.print(f"  #{number:4}  [magenta]{state_str:10}[/]  {display_title}")
    else:
        console.print("  [dim](none)[/]")
    console.print()

    # Blocked Issues section
    console.print(f"[bold cyan]Blocked Issues:[/] {len(blocked_items)}")
    if blocked_items:
        for item in blocked_items:
            number = cast(int, item["number"])
            title = cast(str, item["title"])
            display_title = title[:60] + "..." if len(title) > 60 else title
            console.print(f"  #{number:4}  [red]BLOCKED    [/]  {display_title}")
    else:
        console.print("  [dim](none)[/]")
    console.print()

    # Pool Health section
    console.print("[bold cyan]Pool Health:[/]")
    console.print(f"  Manager-assigned (total): {len(manager_assigned)}")

    # Waiting for governance
    waiting_count = len(waiting_pool)
    if waiting_pool:
        waiting_numbers = [f"#{cast(int, item['number'])}" for item in waiting_pool]
        numbers_str = ", ".join(waiting_numbers)
        console.print(f"  Waiting for governance: {waiting_count}    ({numbers_str})")
    else:
        console.print(f"  Waiting for governance: {waiting_count}")

    # State-missing (governed anomaly)
    anomaly_count = len(governed_anomaly)
    if governed_anomaly:
        anomaly_numbers = [f"#{cast(int, item['number'])}" for item in governed_anomaly]
        numbers_str = ", ".join(anomaly_numbers)
        console.print(
            f"  State-missing (governed anomaly): {anomaly_count}  ({numbers_str})"
        )
    else:
        console.print(f"  State-missing (governed anomaly): {anomaly_count}")


def governance_status(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output in JSON format"),
    ] = False,
    trace: TraceOption = False,
    min_ms: TraceMinMsOption = None,
) -> None:
    """Show governance-focused status: manager-assigned issues,
    RFC/Epic/Blocked counts, and pool health."""
    validate_trace_options(trace, min_ms)
    if trace:
        enable_method_trace(min_ms=min_ms)

    config = load_orchestra_config()

    # Fetch orchestrated issues (reuse existing pipeline)
    service = FlowService()
    flows = service.list_flows(status="active")

    # Get orchestra snapshot for queue status
    orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    queued_set = set(orch_snapshot.queued_issues) if orch_snapshot else set()

    query_service = StatusQueryService(repo=config.repo)
    orchestrated_issues = query_service.fetch_orchestrated_issues(
        flows,
        queued_set,
        stale_flows=[],
        manager_usernames=get_manager_usernames(config),
        supervisor_label=config.supervisor_handoff.issue_label,
    )

    manager_usernames = get_manager_usernames(config)
    supervisor_label = config.supervisor_handoff.issue_label

    # Partition into governance categories
    manager_assigned = [
        item
        for item in orchestrated_issues
        if item.get("assignee") in manager_usernames
    ]

    rfc_items = [
        item
        for item in orchestrated_issues
        if "roadmap/rfc" in cast(list[str], item.get("labels", []))
        and supervisor_label not in cast(list[str], item.get("labels", []))
    ]

    epic_items = [
        item
        for item in orchestrated_issues
        if "roadmap/epic" in cast(list[str], item.get("labels", []))
        and supervisor_label not in cast(list[str], item.get("labels", []))
    ]

    blocked_items = [
        item for item in orchestrated_issues if item.get("state") == IssueState.BLOCKED
    ]

    waiting_pool = [
        item
        for item in orchestrated_issues
        if item.get("state") is None
        and item.get("assignee") in manager_usernames
        and "orchestra-governed" not in cast(list[str], item.get("labels", []))
        and supervisor_label not in cast(list[str], item.get("labels", []))
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
    ]

    governed_anomaly = [
        item
        for item in orchestrated_issues
        if item.get("state") is None
        and item.get("assignee") in manager_usernames
        and "orchestra-governed" in cast(list[str], item.get("labels", []))
        and supervisor_label not in cast(list[str], item.get("labels", []))
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
    ]

    if json_output:
        output_data = {
            "manager_assigned": manager_assigned,
            "rfc_items": rfc_items,
            "epic_items": epic_items,
            "blocked_items": blocked_items,
            "pool_health": {
                "manager_assigned_total": len(manager_assigned),
                "waiting_for_governance": waiting_pool,
                "state_missing_governed_anomaly": governed_anomaly,
            },
        }
        typer.echo(json.dumps(output_data, indent=2, default=str))
    else:
        render_governance_dashboard(
            manager_assigned=manager_assigned,
            rfc_items=rfc_items,
            epic_items=epic_items,
            blocked_items=blocked_items,
            waiting_pool=waiting_pool,
            governed_anomaly=governed_anomaly,
        )
