"""Helpers for syncing flow lifecycle events to issue labels."""

from typing import Any

from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import LabelService


def _is_terminal_flow_status(status: str | None) -> bool:
    """Return whether a flow status is terminal for task closing decisions."""
    return status in {"done", "aborted", "stale"}


def _issue_has_other_open_task_flows(
    store: Any, branch: str, issue_number: int
) -> bool:
    """Check if issue is still bound as task by other non-terminal flows."""
    linked_flows = store.get_flows_by_issue(issue_number, role="task")
    flows = linked_flows if isinstance(linked_flows, list) else []
    for flow in flows:
        other_branch = flow.get("branch")
        if not other_branch or other_branch == branch:
            continue
        flow_status = flow.get("flow_status")
        if not _is_terminal_flow_status(flow_status):
            return True
    return False


def sync_flow_done_task_labels(store: Any, branch: str) -> None:
    """Sync all task-role issues in a flow to state/done."""
    issue_links_raw = store.get_issue_links(branch)
    issue_links = issue_links_raw if isinstance(issue_links_raw, list) else []
    label_service = LabelService()
    for link in issue_links:
        if link.get("issue_role") != "task":
            continue
        issue_number = link.get("issue_number")
        if issue_number is None:
            continue
        if _issue_has_other_open_task_flows(store, branch, int(issue_number)):
            continue
        label_service.confirm_issue_state(
            int(issue_number),
            IssueState.DONE,
            actor="flow:done",
            force=True,
        )


def sync_flow_blocked_task_label(store: Any, branch: str) -> None:
    """Sync task-role issues in a flow to state/blocked when flow is blocked."""
    issue_links_raw = store.get_issue_links(branch)
    issue_links = issue_links_raw if isinstance(issue_links_raw, list) else []
    label_service = LabelService()
    for link in issue_links:
        if link.get("issue_role") != "task":
            continue
        issue_number = link.get("issue_number")
        if issue_number is None:
            continue
        label_service.confirm_issue_state(
            int(issue_number),
            IssueState.BLOCKED,
            actor="flow:blocked",
            force=True,
        )
