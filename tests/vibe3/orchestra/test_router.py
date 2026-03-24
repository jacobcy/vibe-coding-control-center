"""Tests for Orchestra router."""

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.models import IssueInfo
from vibe3.orchestra.router import Router


def test_route_ready_to_claimed():
    router = Router()
    issue = IssueInfo(number=42, title="Test", state=IssueState.CLAIMED)
    trigger = router.route(issue, IssueState.READY)

    assert trigger is not None
    assert trigger.command == "plan"
    assert trigger.from_state == IssueState.READY
    assert trigger.to_state == IssueState.CLAIMED


def test_route_claimed_to_in_progress():
    router = Router()
    issue = IssueInfo(number=42, title="Test", state=IssueState.IN_PROGRESS)
    trigger = router.route(issue, IssueState.CLAIMED)

    assert trigger is not None
    assert trigger.command == "run"


def test_route_in_progress_to_review():
    router = Router()
    issue = IssueInfo(number=42, title="Test", state=IssueState.REVIEW)
    trigger = router.route(issue, IssueState.IN_PROGRESS)

    assert trigger is not None
    assert trigger.command == "review"


def test_route_no_state_change():
    router = Router()
    issue = IssueInfo(number=42, title="Test", state=IssueState.READY)
    trigger = router.route(issue, IssueState.READY)

    assert trigger is None


def test_route_no_trigger_defined():
    router = Router()
    issue = IssueInfo(number=42, title="Test", state=IssueState.DONE)
    trigger = router.route(issue, IssueState.REVIEW)

    assert trigger is None


def test_route_none_state():
    router = Router()
    issue = IssueInfo(number=42, title="Test", state=None)
    trigger = router.route(issue, IssueState.READY)

    assert trigger is None
