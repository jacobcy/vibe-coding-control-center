"""Service layer for task status dashboard data fetching and classification."""

from __future__ import annotations

from collections import namedtuple
from typing import TYPE_CHECKING, Any, cast

from vibe3.models import FlowStatusResponse, IssueState, OrchestraConfig
from vibe3.services.shared import (
    StatusQueryService,
    has_orchestra_governed,
    has_roadmap_label,
    is_auto_task_branch,
    is_dev_collab_branch,
    normalize_labels,
)
from vibe3.services.task.classifier import TaskStatusBucket, classify_task_status

if TYPE_CHECKING:
    pass


NON_ACTIVE_TASK_FLOW_STATUSES = frozenset({"done", "review", "failed", "aborted"})

# Module-private carrier for the three-step fetch sequence.
# Not exported — callers should call build_api_task_data (HTTP) or
# perform_status_fetch (CLI dashboard), never reach into this tuple.
_StatusFetchResult = namedtuple(
    "_StatusFetchResult",
    ["config", "orch_snapshot", "snapshot_found", "flows", "orchestrated_issues"],
)


def perform_status_fetch(all_flows: bool = False) -> _StatusFetchResult:
    """Run the three-step fetch sequence; return a private namedtuple.

    Kept separate from build_api_task_data so the CLI dashboard can
    reuse the same I/O flows without going through the JSON-clean dict.
    """
    import time

    from vibe3.config import get_manager_usernames, load_orchestra_config
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
    from vibe3.services.flow import FlowService

    service = FlowService()  # type: ignore[assignment]
    flows = service.list_flows(status=None if all_flows else "active")
    if not all_flows:
        flows.extend(service.list_flows(status="done"))
        flows.extend(service.list_flows(status="blocked"))

    stale_flows = service.list_flows(status="stale") if not all_flows else []

    # Fetch review/failed/aborted flows for issue-to-flow mapping.
    # Batched into one SQL WHERE flow_status IN (...) round-trip (Issue #3189).
    # These are terminal states with PRs that should show in "Flows with PRs" section.
    extra_flows: list[FlowStatusResponse] = []
    if not all_flows:
        extra_flows = service.list_flows(statuses=["review", "failed", "aborted"])

    # Fetch orchestrated issues
    queued_set = set(orch_snapshot.queued_issues)
    query_service = StatusQueryService(repo=config.repo)
    orchestrated_issues = query_service.fetch_orchestrated_issues(
        flows,
        queued_set,
        stale_flows=stale_flows,
        extra_flows=extra_flows,
        manager_usernames=get_manager_usernames(config),
        supervisor_label=config.supervisor_handoff.issue_label,
    )

    return _StatusFetchResult(
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
    from vibe3.config import get_manager_usernames

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
        flow = cast(FlowStatusResponse | None, item.get("flow"))
        if flow and flow.flow_status in NON_ACTIVE_TASK_FLOW_STATUSES:
            continue
        if state == IssueState.DONE:
            continue
        # Blocked issues have dedicated section, skip bucketing
        if state == IssueState.BLOCKED:
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


def _flow_to_dict(flow: FlowStatusResponse) -> dict[str, Any]:
    """Convert FlowStatusResponse to JSON-serializable dict."""
    return flow.model_dump(mode="json")


def _issue_to_dict(item: dict[str, object]) -> dict[str, Any]:
    """Convert issue item to JSON-serializable dict with all required fields."""
    flow = cast(FlowStatusResponse | None, item.get("flow"))
    state = cast(IssueState | None, item.get("state"))
    verdict = item.get("latest_verdict")

    result: dict[str, Any] = {
        "number": cast(int, item.get("number")),
        "title": cast(str, item.get("title", "")),
        "state": state.value if state else None,
        "assignee": cast(str | None, item.get("assignee")),
        "flow_branch": flow.branch if flow else None,
        "queue_rank": cast(int | None, item.get("queue_rank")),
        "plan_ref": flow.plan_ref if flow else None,
        "report_ref": flow.report_ref if flow else None,
        "audit_ref": flow.audit_ref if flow else None,
        "blocked_by": cast(tuple[int, ...] | None, item.get("blocked_by")),
        "blocked_reason": cast(str | None, item.get("blocked_reason")),
        "priority": cast(int | None, item.get("priority")),
        "roadmap": cast(str | None, item.get("roadmap")),
        "remote": cast(bool, item.get("remote", False)),
        "labels": cast(list[str], item.get("labels", [])),
    }

    # Convert verdict
    if verdict is not None:
        from vibe3.models import VerdictRecord

        if isinstance(verdict, VerdictRecord):
            result["verdict"] = {
                "verdict": verdict.verdict,  # Already a string Literal
                "actor": verdict.actor,
                "role": verdict.role,
                "timestamp": (
                    verdict.timestamp.isoformat() if verdict.timestamp else None
                ),
                "reason": verdict.reason,
                "issues": verdict.issues,
            }
        else:
            result["verdict"] = verdict
    else:
        result["verdict"] = None

    return result


def build_api_task_data(all_flows: bool = False) -> dict[str, Any]:
    """Build JSON-serializable task status data for API endpoint.

    Args:
        all_flows: If True, include all flow statuses;
            otherwise active/done/blocked only.

    Returns:
        Dict with config_summary, server_status, classified_issues, flows.
    """
    data = perform_status_fetch(all_flows)
    classified = classify_task_issues_for_rendering(
        data.orchestrated_issues, data.config
    )

    # Config summary
    config_summary = {
        "repo": data.config.repo,
        "port": data.config.port,
        "polling_interval": data.config.polling_interval,
        "max_concurrent_flows": data.config.max_concurrent_flows,
    }

    # Server status
    server_status = {
        "running": data.orch_snapshot.server_running,
        "snapshot_found": data.snapshot_found,
        "polling_interval": data.orch_snapshot.polling_interval,
        "port": data.orch_snapshot.port,
        "active_issues": [
            {
                "number": issue.number,
                "state": issue.state.value if issue.state else None,
            }
            for issue in data.orch_snapshot.active_issues
        ],
        "queued_issues": list(data.orch_snapshot.queued_issues),
        "active_flows": data.orch_snapshot.active_flows,
        "active_worktrees": data.orch_snapshot.active_worktrees,
    }

    # Convert classified issues - bucketed_items needs special handling
    classified_issues: dict[str, Any] = {}

    # Convert simple lists
    for key in [
        "supervisor_items",
        "roadmap_rfc_items",
        "roadmap_epic_items",
        "waiting_for_pool_items",
        "governed_anomaly_items",
        "human_collab_items",
        "task_progress_items",
        "remote_items",
        "pr_ref_items",
        "blocked_items",
    ]:
        classified_issues[key] = [_issue_to_dict(item) for item in classified[key]]

    # Convert bucketed_items (dict with TaskStatusBucket keys)
    bucketed: dict[str, list[dict[str, Any]]] = {}
    for bucket, items in classified["bucketed_items"].items():
        bucket_key = bucket.value if hasattr(bucket, "value") else str(bucket)
        bucketed[bucket_key] = [_issue_to_dict(item) for item in items]
    classified_issues["bucketed_items"] = bucketed

    # Convert open_issue_numbers (set to list)
    classified_issues["open_issue_numbers"] = list(classified["open_issue_numbers"])

    # Convert flows
    flows = [_flow_to_dict(flow) for flow in data.flows]

    return {
        "config_summary": config_summary,
        "server_status": server_status,
        "classified_issues": classified_issues,
        "flows": flows,
    }
