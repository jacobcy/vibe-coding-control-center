"""Pure task status classification helpers for status dashboards."""

from __future__ import annotations

from enum import Enum

from vibe3.models.orchestration import IssueState


class TaskStatusBucket(str, Enum):
    """Canonical task status buckets used by status dashboards."""

    ASSIGNEE_INTAKE = "assignee-intake"
    READY_QUEUE = "ready-queue"
    READY_ANOMALY = "ready-anomaly"
    OTHER = "other"


def has_manager_assignee(assignee: str | None) -> bool:
    """Whether the issue has a usable primary manager assignee."""
    return bool(assignee and assignee.strip())


def classify_task_status(
    state: IssueState | None,
    assignee: str | None,
) -> TaskStatusBucket:
    """Classify a task into the shared status buckets.

    Semantics:
    - assignee is the intake signal
    - state/ready is the queue signal
    - state/ready without assignee is an anomaly / historical debt
    - non-ready states stay in intake view even if assignee is missing, because
      runtime only treats missing assignee on READY as a governance boundary
      violation
    """
    if state == IssueState.READY:
        if not has_manager_assignee(assignee):
            return TaskStatusBucket.READY_ANOMALY
        return TaskStatusBucket.READY_QUEUE

    if state in {
        IssueState.CLAIMED,
        IssueState.HANDOFF,
        IssueState.IN_PROGRESS,
        IssueState.REVIEW,
        IssueState.BLOCKED,
    }:
        return TaskStatusBucket.ASSIGNEE_INTAKE

    return TaskStatusBucket.OTHER
