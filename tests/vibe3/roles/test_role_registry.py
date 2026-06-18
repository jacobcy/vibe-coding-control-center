"""Tests for role registry dispatch helpers."""

from vibe3.domain.events.flow_lifecycle import (
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


class TestBuildLabelDispatchEvent:
    """Tests for role registry dispatch helpers."""

    def test_build_label_dispatch_event_for_manager(self):
        event = build_label_dispatch_event(
            MANAGER_ROLE,
            _issue(),
            branch="task/issue-42",
        )

        assert isinstance(event, ManagerDispatchIntent)
        assert event.issue_number == 42
        assert event.branch == "task/issue-42"
        assert event.trigger_state == IssueState.READY.value

    def test_build_label_dispatch_event_for_plan(self):
        event = build_label_dispatch_event(
            PLANNER_ROLE,
            _issue(),
            branch="task/issue-42",
        )

        assert isinstance(event, PlannerDispatchIntent)
        assert event.branch == "task/issue-42"
        assert event.trigger_state == IssueState.CLAIMED.value

    def test_build_label_dispatch_event_for_run(self):
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

    def test_build_label_dispatch_event_for_review(self):
        event = build_label_dispatch_event(
            REVIEWER_ROLE,
            _issue(),
            branch="task/issue-42",
        )

        assert isinstance(event, ReviewerDispatchIntent)
        assert event.trigger_state == IssueState.REVIEW.value
        # Reviewer-specific context is NOT on the dispatch intent
        assert not hasattr(event, "report_ref")
