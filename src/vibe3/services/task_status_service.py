#!/usr/bin/env python3
"""Task status service - business logic for task status dashboard."""

from typing import Any, cast

from vibe3.commands import _validate_pid_file
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueState
from vibe3.services.flow_service import FlowService
from vibe3.services.orchestra_helpers import get_manager_usernames
from vibe3.services.orchestra_status_service import OrchestraStatusService
from vibe3.services.status_query_service import (
    StatusQueryService,
    is_auto_task_branch,
)
from vibe3.services.task_status_classifier import (
    TaskStatusBucket,
    classify_task_status,
)


def _include_issue_in_task_progress(item: dict[str, object]) -> bool:
    """Only auto-task flows should participate in task-oriented Issue Progress."""
    flow = cast(FlowStatusResponse | None, item.get("flow"))
    state = cast(IssueState, item["state"])

    if flow is None:
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


def fetch_task_status_data(all_flows: bool = False) -> dict[str, Any]:
    """Fetch all data needed for task status dashboard."""
    import time

    config = load_orchestra_config()
    orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    if orch_snapshot is None:
        time.sleep(0.5)
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)

    if not orch_snapshot:
        _, pid_alive = _validate_pid_file(config.pid_file)
        if pid_alive:
            time.sleep(0.5)
            orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)

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

    return {
        "config": config,
        "orch_snapshot": orch_snapshot,
        "orchestrated_issues": orchestrated_issues,
        "flows": flows,
    }


def classify_task_issues(
    orchestrated_issues: list[dict[str, object]],
    config: OrchestraConfig,
) -> dict[str, Any]:
    """Classify issues into categories for rendering."""
    supervisor_label = config.supervisor_handoff.issue_label

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

    pr_ref_items = [
        item
        for item in task_progress_items
        if item.get("flow") and getattr(item["flow"], "pr_ref", None)
    ]

    blocked_items = [
        item
        for item in orchestrated_issues
        if cast(IssueState, item["state"]) == IssueState.BLOCKED
        and "roadmap/rfc" not in cast(list[str], item.get("labels", []))
        and "roadmap/epic" not in cast(list[str], item.get("labels", []))
        and cast(int, item["number"]) not in supervisor_numbers
    ]

    return {
        "supervisor_items": supervisor_items,
        "roadmap_rfc_items": roadmap_rfc_items,
        "roadmap_epic_items": roadmap_epic_items,
        "waiting_for_pool_items": waiting_for_pool_items,
        "governed_anomaly_items": governed_anomaly_items,
        "bucketed_items": bucketed_items,
        "remote_items": remote_items,
        "pr_ref_items": pr_ref_items,
        "blocked_items": blocked_items,
    }
