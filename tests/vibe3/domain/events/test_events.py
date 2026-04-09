"""Tests for domain events data structures."""

from vibe3.domain.events.flow_lifecycle import (
    ExecutionCompleted,
    PlanCompleted,
    ReviewCompleted,
)
from vibe3.domain.events.manager import ManagerFlowDispatched


def test_execution_completed_event_structure() -> None:
    """Test ExecutionCompleted event has correct structure."""
    event = ExecutionCompleted(
        issue_number=42,
        branch="task/issue-42",
        actor="agent:executor",
    )

    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.actor == "agent:executor"
    assert event.timestamp is None


def test_execution_completed_with_timestamp() -> None:
    """Test ExecutionCompleted event with custom timestamp."""
    event = ExecutionCompleted(
        issue_number=42,
        branch="task/issue-42",
        actor="agent:executor",
        timestamp="2026-04-09T12:00:00Z",
    )

    assert event.timestamp == "2026-04-09T12:00:00Z"


def test_plan_completed_event_structure() -> None:
    """Test PlanCompleted event has correct structure."""
    event = PlanCompleted(
        issue_number=42,
        branch="task/issue-42",
        actor="agent:plan",
    )

    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.actor == "agent:plan"


def test_review_completed_event_structure() -> None:
    """Test ReviewCompleted event has correct structure."""
    event = ReviewCompleted(
        issue_number=42,
        branch="task/issue-42",
        verdict="approved",
        actor="agent:review",
    )

    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.verdict == "approved"
    assert event.actor == "agent:review"


def test_manager_flow_dispatched_event_structure() -> None:
    """Test ManagerFlowDispatched event has correct structure."""
    event = ManagerFlowDispatched(
        issue_number=42,
        branch="task/issue-42",
        tmux_session="vibe3-manager-42",
        actor="agent:manager",
    )

    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.tmux_session == "vibe3-manager-42"
    assert event.actor == "agent:manager"
