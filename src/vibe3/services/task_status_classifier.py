"""Pure task status classification helpers for status dashboards."""

from __future__ import annotations

from enum import Enum

from vibe3.models.orchestration import IssueState
from vibe3.utils.label_utils import has_manager_assignee


class TaskStatusBucket(str, Enum):
    """Canonical task status buckets used by status dashboards."""

    ASSIGNEE_INTAKE = "assignee-intake"
    READY_QUEUE = "ready-queue"
    READY_ANOMALY = "ready-anomaly"
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
    - non-ready states stay in intake view even if assignee is missing, because
      runtime only treats missing assignee on READY as a governance boundary
      violation
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
    }:
        return TaskStatusBucket.ASSIGNEE_INTAKE

    return TaskStatusBucket.OTHER
