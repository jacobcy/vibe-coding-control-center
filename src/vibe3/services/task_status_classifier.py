"""Pure task status classification helpers for status dashboards.

Filtering rules: docs/v3/orchestra/task-status-filtering.md
"""

from __future__ import annotations

from enum import Enum

from vibe3.models.orchestration import IssueState
from vibe3.services.label_utils import has_manager_assignee


class TaskStatusBucket(str, Enum):
    """Canonical task status buckets used by status dashboards."""

    ASSIGNEE_INTAKE = "assignee-intake"
    READY_QUEUE = "ready-queue"
    READY_ANOMALY = "ready-anomaly"
    ACTIVE_ANOMALY = "active-anomaly"
    OTHER = "other"


def classify_task_status(
    state: IssueState | None,
    assignee: str | None,
    manager_usernames: list[str] | tuple[str, ...],
) -> TaskStatusBucket:
    """Classify a task into the shared status buckets.

    Semantics:
    - manager assignee is the intake/queue signal
    - state/ready with non-manager assignee is an anomaly
    - state/ready without assignee is an anomaly / historical debt
    - blocked has dedicated section in status dashboard
    - active states (claimed/in-progress/etc) without assignee are anomalies:
      state exists but no one is responsible
    """
    if state == IssueState.READY:
        # Missing assignee is always an anomaly, regardless of manager_usernames
        if not assignee or not assignee.strip():
            return TaskStatusBucket.READY_ANOMALY
        # Non-manager assignee is also an anomaly
        if not has_manager_assignee(
            [assignee],
            manager_usernames,
        ):
            return TaskStatusBucket.READY_ANOMALY
        return TaskStatusBucket.READY_QUEUE

    if state == IssueState.BLOCKED:
        # Blocked issues have dedicated section in status dashboard,
        # exclude from intake to avoid duplication
        return TaskStatusBucket.OTHER

    if state in {
        IssueState.CLAIMED,
        IssueState.HANDOFF,
        IssueState.IN_PROGRESS,
        IssueState.REVIEW,
        IssueState.MERGE_READY,
    }:
        # Active state without assignee is an anomaly (rule 2)
        if not assignee or not assignee.strip():
            return TaskStatusBucket.ACTIVE_ANOMALY
        return TaskStatusBucket.ASSIGNEE_INTAKE

    return TaskStatusBucket.OTHER
