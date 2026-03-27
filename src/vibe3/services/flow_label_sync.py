"""Helpers for syncing flow lifecycle events to issue labels."""

from typing import Any

from vibe3.models.orchestration import IssueState
from vibe3.services.label_service import LabelService


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
        label_service.confirm_issue_state(
            int(issue_number),
            IssueState.DONE,
            actor="flow:done",
            force=True,
        )


def sync_flow_blocked_task_label(flow_data: dict[str, Any]) -> None:
    """Sync bound task issue to state/blocked when flow is blocked."""
    task_issue_number = flow_data.get("task_issue_number")
    if task_issue_number is None:
        return
    LabelService().confirm_issue_state(
        int(task_issue_number),
        IssueState.BLOCKED,
        actor="flow:blocked",
        force=True,
    )
