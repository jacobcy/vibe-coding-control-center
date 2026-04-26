"""Tests for role registry dispatch helpers."""

from vibe3.domain.events import (
    ExecutorDispatchIntent,
    ManagerDispatchIntent,
    PlannerDispatchIntent,
    ReviewerDispatchIntent,
)
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.manager import MANAGER_ROLE
from vibe3.roles.plan import PLANNER_ROLE
from vibe3.roles.registry import build_label_dispatch_event
from vibe3.roles.review import REVIEWER_ROLE
from vibe3.roles.run import EXECUTOR_ROLE


def _issue(number: int = 42) -> IssueInfo:
    return IssueInfo(
        number=number,
        title=f"Issue {number}",
        state=IssueState.CLAIMED,
        labels=[],
        assignees=[],
    )


def test_build_label_dispatch_event_for_manager():
    event = build_label_dispatch_event(
        MANAGER_ROLE,
        _issue(),
        branch="task/issue-42",
    )

    assert isinstance(event, ManagerDispatchIntent)
    assert event.issue_number == 42
    assert event.branch == "task/issue-42"
    assert event.trigger_state == IssueState.READY.value


def test_build_label_dispatch_event_for_plan():
    event = build_label_dispatch_event(
        PLANNER_ROLE,
        _issue(),
        branch="task/issue-42",
    )

    assert isinstance(event, PlannerDispatchIntent)
    assert event.branch == "task/issue-42"
    assert event.trigger_state == IssueState.CLAIMED.value


def test_build_label_dispatch_event_for_run():
    event = build_label_dispatch_event(
        EXECUTOR_ROLE,
        _issue(),
        branch="task/issue-42",
    )

    assert isinstance(event, ExecutorDispatchIntent)
    assert event.trigger_state == IssueState.IN_PROGRESS.value
    # Executor-specific context is NOT on the dispatch intent
    assert not hasattr(event, "plan_ref")
    assert not hasattr(event, "commit_mode")


def test_build_label_dispatch_event_for_review():
    event = build_label_dispatch_event(
        REVIEWER_ROLE,
        _issue(),
        branch="task/issue-42",
    )

    assert isinstance(event, ReviewerDispatchIntent)
    assert event.trigger_state == IssueState.REVIEW.value
    # Reviewer-specific context is NOT on the dispatch intent
    assert not hasattr(event, "report_ref")


def test_planner_dispatch_predicate_ignores_plan_ref() -> None:
    assert PLANNER_ROLE.dispatch_predicate({}, False) is True
    assert PLANNER_ROLE.dispatch_predicate({"plan_ref": "plan.md"}, False) is True
    assert PLANNER_ROLE.dispatch_predicate({}, True) is False


def test_executor_dispatch_predicate_ignores_report_ref() -> None:
    assert EXECUTOR_ROLE.dispatch_predicate({}, False) is True
    assert EXECUTOR_ROLE.dispatch_predicate({"report_ref": "report.md"}, False) is True
    assert EXECUTOR_ROLE.dispatch_predicate({}, True) is False


def test_reviewer_dispatch_predicate_ignores_audit_ref() -> None:
    assert REVIEWER_ROLE.dispatch_predicate({}, False) is True
    assert REVIEWER_ROLE.dispatch_predicate({"audit_ref": "audit.md"}, False) is True
    assert REVIEWER_ROLE.dispatch_predicate({}, True) is False
