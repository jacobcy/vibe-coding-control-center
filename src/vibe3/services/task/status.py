"""Service layer for task status dashboard data fetching and classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from vibe3.models import FlowStatusResponse, IssueState, OrchestraConfig
from vibe3.services import (
    StatusQueryService,
    is_auto_task_branch,
    is_dev_collab_branch,
)
from vibe3.services.orchestra.status import OrchestraSnapshot
from vibe3.services.shared.labels import (
    has_orchestra_governed,
    has_roadmap_label,
    normalize_labels,
)
from vibe3.services.task.classifier import TaskStatusBucket, classify_task_status

if TYPE_CHECKING:
    pass


@dataclass
class TaskStatusData:
    """Container for all data needed by task status dashboard."""

    config: OrchestraConfig
    orch_snapshot: OrchestraSnapshot
    snapshot_found: bool
    flows: list[FlowStatusResponse]
    orchestrated_issues: list[dict[str, object]]


def fetch_task_status_data(
    all_flows: bool = False,
) -> TaskStatusData:
    """Fetch all data needed for task status dashboard.

    Args:
        all_flows: If True, include all flow statuses;
            otherwise active/done/blocked only.

    Returns:
        TaskStatusData containing config, snapshot, flows, and issues.
    """
    import time

    from vibe3.config import load_orchestra_config
    from vibe3.services.orchestra.helpers import get_manager_usernames
    from vibe3.services.orchestra.orchestrator import FlowOrchestratorService
    from vibe3.services.orchestra.status import OrchestraStatusService

    config = load_orchestra_config()
    orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)

    # Retry logic for snapshot
    if orch_snapshot is None:
        time.sleep(0.5)
        orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
    snapshot_found = orch_snapshot is not None

    if not orch_snapshot:
        from vibe3.utils import read_instance_info, validate_instance

        info = read_instance_info(config.pid_file)
        pid_alive = validate_instance(info) if info else False
        if pid_alive:
            time.sleep(0.5)
            orch_snapshot = OrchestraStatusService.fetch_live_snapshot(config)
            snapshot_found = orch_snapshot is not None

    if not orch_snapshot:
        from dataclasses import replace

        orch_service = OrchestraStatusService(
            config, orchestrator=FlowOrchestratorService(config)
        )
        local_snap = orch_service.snapshot()
        orch_snapshot = replace(local_snap, server_running=False)

    # Assert orch_snapshot is non-None after fallback
    assert orch_snapshot is not None

    # Fetch flows
    from vibe3.services.flow.service import FlowService

    service = FlowService()  # type: ignore[assignment]
    flows = service.list_flows(status=None if all_flows else "active")
    if not all_flows:
        flows.extend(service.list_flows(status="done"))
        flows.extend(service.list_flows(status="blocked"))

    stale_flows = service.list_flows(status="stale") if not all_flows else []

    # Fetch orchestrated issues
    queued_set = set(orch_snapshot.queued_issues)
    query_service = StatusQueryService(repo=config.repo)
    orchestrated_issues = query_service.fetch_orchestrated_issues(
        flows,
        queued_set,
        stale_flows=stale_flows,
        manager_usernames=get_manager_usernames(config),
        supervisor_label=config.supervisor_handoff.issue_label,
    )

    return TaskStatusData(
        config=config,
        orch_snapshot=orch_snapshot,
        snapshot_found=snapshot_found,
        flows=flows,
        orchestrated_issues=orchestrated_issues,
    )


def _include_issue_in_task_progress(item: dict[str, object]) -> bool:
    """Only auto-task flows should participate in task-oriented Issue Progress."""
    flow = cast(FlowStatusResponse | None, item.get("flow"))
    state = cast(IssueState | None, item.get("state"))

    if flow is None:
        # Include issues without flow if they are remote (claimed by manager)
        # or in states that should show even without flow
        is_remote = cast(bool, item.get("remote", False))
        if is_remote:
            return True
        # State can be None; only check if present
        if state is None:
            return False
        return state in {
            IssueState.READY,
            IssueState.HANDOFF,
            IssueState.BLOCKED,
            IssueState.DONE,
            IssueState.CLAIMED,
            IssueState.IN_PROGRESS,
            IssueState.REVIEW,
            IssueState.MERGE_READY,
        }
    return is_auto_task_branch(flow.branch)


def _is_dev_collab_item(item: dict[str, object]) -> bool:
    """Check if item belongs to a human-collaboration dev/issue-N flow."""
    flow = cast(FlowStatusResponse | None, item.get("flow"))
    if flow is None:
        return False
    return is_dev_collab_branch(flow.branch)


def classify_task_issues_for_rendering(
    orchestrated_issues: list[dict[str, object]],
    config: OrchestraConfig,
) -> dict[str, Any]:
    """Classify orchestrated issues into rendering categories.

    Args:
        orchestrated_issues: List of issue dicts from StatusQueryService.
        config: Orchestra configuration.

    Returns:
        Dict with keys: supervisor_items, roadmap_rfc_items, roadmap_epic_items,
        waiting_for_pool_items, governed_anomaly_items, task_progress_items,
        remote_items, bucketed_items, pr_ref_items, blocked_items,
        open_issue_numbers.
    """
    from vibe3.services.orchestra.helpers import get_manager_usernames

    supervisor_label = config.supervisor_handoff.issue_label
    manager_usernames = get_manager_usernames(config)

    # Filter supervisor items
    supervisor_items = [
        item
        for item in orchestrated_issues
        if supervisor_label in normalize_labels(item.get("labels", []))
    ]
    supervisor_numbers = {cast(int, item["number"]) for item in supervisor_items}

    # Filter RFC items
    roadmap_rfc_items = [
        item
        for item in orchestrated_issues
        if "roadmap/rfc" in normalize_labels(item.get("labels", []))
        and supervisor_label not in normalize_labels(item.get("labels", []))
    ]
    roadmap_rfc_numbers = {cast(int, item["number"]) for item in roadmap_rfc_items}

    # Filter epic items
    roadmap_epic_items = [
        item
        for item in orchestrated_issues
        if "roadmap/epic" in normalize_labels(item.get("labels", []))
        and supervisor_label not in normalize_labels(item.get("labels", []))
    ]
    roadmap_epic_numbers = {cast(int, item["number"]) for item in roadmap_epic_items}

    # Split missing state items into two categories
    waiting_for_pool_items = [
        item
        for item in orchestrated_issues
        if item.get("state") is None
        and item.get("assignee") is not None
        and item.get("assignee") in manager_usernames
        and supervisor_label not in normalize_labels(item.get("labels", []))
        and not has_roadmap_label(normalize_labels(item.get("labels", [])))
        and not has_orchestra_governed(normalize_labels(item.get("labels", [])))
    ]
    governed_anomaly_items = [
        item
        for item in orchestrated_issues
        if item.get("state") is None
        and item.get("assignee") is not None
        and item.get("assignee") in manager_usernames
        and supervisor_label not in normalize_labels(item.get("labels", []))
        and not has_roadmap_label(normalize_labels(item.get("labels", [])))
        and has_orchestra_governed(normalize_labels(item.get("labels", [])))
    ]
    missing_state_numbers = {
        cast(int, item["number"])
        for item in waiting_for_pool_items + governed_anomaly_items
    }

    # Filter human collaboration items (dev/issue-* branches)
    human_collab_items = [
        item
        for item in orchestrated_issues
        if _is_dev_collab_item(item)
        and cast(int, item["number"]) not in supervisor_numbers
        and cast(int, item["number"]) not in roadmap_rfc_numbers
        and cast(int, item["number"]) not in roadmap_epic_numbers
        and cast(int, item["number"]) not in missing_state_numbers
    ]
    human_collab_numbers = {cast(int, item["number"]) for item in human_collab_items}

    # Filter task progress items
    task_progress_items = [
        item
        for item in orchestrated_issues
        if _include_issue_in_task_progress(item)
        and cast(int, item["number"]) not in supervisor_numbers
        and cast(int, item["number"]) not in roadmap_rfc_numbers
        and cast(int, item["number"]) not in roadmap_epic_numbers
        and cast(int, item["number"]) not in missing_state_numbers
    ]

    # Separate remote and non-remote items
    remote_items = [
        item
        for item in task_progress_items
        if cast(bool, item.get("remote"))
        and cast(IssueState, item["state"]) != IssueState.BLOCKED
    ]
    non_remote_items = [
        item for item in task_progress_items if not cast(bool, item.get("remote"))
    ]

    # Bucket non-remote items by status
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
            manager_usernames,
        )
        bucketed_items[bucket].append(item)

    # Filter PR ref items
    pr_ref_items = [
        item
        for item in task_progress_items
        if item.get("flow") and getattr(item["flow"], "pr_ref", None)
    ]

    # Filter blocked items
    blocked_items = [
        item
        for item in orchestrated_issues
        if cast(IssueState, item["state"]) == IssueState.BLOCKED
        and not has_roadmap_label(normalize_labels(item.get("labels", [])))
        and cast(int, item["number"]) not in supervisor_numbers
        and cast(int, item["number"]) not in human_collab_numbers
    ]

    # Build set of open issue numbers for dependency status checking
    # Filter out DONE issues since they're no longer blocking
    open_issue_numbers: set[int] = {
        cast(int, issue["number"])
        for issue in orchestrated_issues
        if cast(IssueState | None, issue.get("state")) != IssueState.DONE
    }

    return {
        "supervisor_items": supervisor_items,
        "roadmap_rfc_items": roadmap_rfc_items,
        "roadmap_epic_items": roadmap_epic_items,
        "waiting_for_pool_items": waiting_for_pool_items,
        "governed_anomaly_items": governed_anomaly_items,
        "human_collab_items": human_collab_items,
        "task_progress_items": task_progress_items,
        "remote_items": remote_items,
        "bucketed_items": bucketed_items,
        "pr_ref_items": pr_ref_items,
        "blocked_items": blocked_items,
        "open_issue_numbers": open_issue_numbers,
    }
