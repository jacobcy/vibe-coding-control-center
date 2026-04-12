"""Tests for role registry dispatch helpers."""

from vibe3.domain.events import (
    ExecutorDispatched,
    PlannerDispatched,
    ReviewerDispatched,
)
from vibe3.domain.events.flow_lifecycle import IssueStateChanged
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
        flow_state={},
    )

    assert isinstance(event, IssueStateChanged)
    assert event.to_state == IssueState.READY.value


def test_build_label_dispatch_event_for_plan():
    event = build_label_dispatch_event(
        PLANNER_ROLE,
        _issue(),
        branch="task/issue-42",
        flow_state={},
    )

    assert isinstance(event, PlannerDispatched)
    assert event.branch == "task/issue-42"
    assert event.trigger_state == IssueState.CLAIMED.value


def test_build_label_dispatch_event_for_run_includes_plan_ref():
    event = build_label_dispatch_event(
        EXECUTOR_ROLE,
        _issue(),
        branch="task/issue-42",
        flow_state={"plan_ref": "plan.md"},
    )

    assert isinstance(event, ExecutorDispatched)
    assert event.plan_ref == "plan.md"
    assert event.trigger_state == IssueState.IN_PROGRESS.value


def test_build_label_dispatch_event_for_review_includes_report_ref():
    event = build_label_dispatch_event(
        REVIEWER_ROLE,
        _issue(),
        branch="task/issue-42",
        flow_state={"report_ref": "report.md"},
    )

    assert isinstance(event, ReviewerDispatched)
    assert event.report_ref == "report.md"
    assert event.trigger_state == IssueState.REVIEW.value
