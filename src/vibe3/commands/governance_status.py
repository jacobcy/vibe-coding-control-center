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

    from vibe3.commands.status_render import render_governance_dashboard

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
