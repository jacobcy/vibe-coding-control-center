"""Tests for Orchestra models."""

from vibe3.models.orchestration import IssueState
from vibe3.orchestra.models import IssueInfo, Trigger


def test_issue_info_slug():
    issue = IssueInfo(number=42, title="Fix login redirect bug", state=None)
    assert issue.slug == "fix-login-redirect-bug"


def test_issue_info_slug_special_chars():
    issue = IssueInfo(number=42, title="Add @mention support!!!", state=None)
    assert issue.slug == "add-mention-support"


def test_trigger_key():
    issue = IssueInfo(number=42, title="Test", state=IssueState.CLAIMED)
    trigger = Trigger(
        issue=issue,
        from_state=IssueState.READY,
        to_state=IssueState.CLAIMED,
        command="plan",
    )
    assert trigger.trigger_key == "ready->claimed"


def test_trigger_key_none_from_state():
    issue = IssueInfo(number=42, title="Test", state=IssueState.CLAIMED)
    trigger = Trigger(
        issue=issue,
        from_state=None,
        to_state=IssueState.CLAIMED,
        command="plan",
    )
    assert trigger.trigger_key == "none->claimed"
