"""Tests for the shared task status classifier."""

from vibe3.models.orchestration import IssueState
from vibe3.services.task_status_classifier import (
    TaskStatusBucket,
    classify_task_status,
)


def test_classify_task_status_prioritizes_assignee_intake_before_ready() -> None:
    """Non-ready assigned issues should classify as intake."""
    assert (
        classify_task_status(IssueState.CLAIMED, "manager-bot")
        == TaskStatusBucket.ASSIGNEE_INTAKE
    )


def test_classify_task_status_marks_ready_with_assignee_as_queue() -> None:
    """READY issues with assignee should stay in the ready queue."""
    assert (
        classify_task_status(IssueState.READY, "manager-bot")
        == TaskStatusBucket.READY_QUEUE
    )


def test_classify_task_status_marks_ready_without_assignee_as_anomaly() -> None:
    """READY issues without assignee are governance anomalies."""
    assert (
        classify_task_status(IssueState.READY, None) == TaskStatusBucket.READY_ANOMALY
    )


def test_classify_task_status_marks_ready_with_blank_assignee_as_anomaly() -> None:
    """Blank assignee values should not count as intake success."""
    assert (
        classify_task_status(IssueState.READY, "   ") == TaskStatusBucket.READY_ANOMALY
    )


def test_classify_task_status_keeps_non_ready_unassigned_in_intake_view() -> None:
    """Only READY without assignee is treated as a queue anomaly."""
    assert (
        classify_task_status(IssueState.HANDOFF, None)
        == TaskStatusBucket.ASSIGNEE_INTAKE
    )


def test_classify_task_status_blocked_maps_to_assignee_intake() -> None:
    """BLOCKED issues without flow map to Assignee Intake."""
    assert (
        classify_task_status(IssueState.BLOCKED, None)
        == TaskStatusBucket.ASSIGNEE_INTAKE
    )


def test_classify_task_status_failed_maps_to_assignee_intake() -> None:
    """FAILED issues without flow map to Assignee Intake."""
    assert (
        classify_task_status(IssueState.FAILED, None)
        == TaskStatusBucket.ASSIGNEE_INTAKE
    )
