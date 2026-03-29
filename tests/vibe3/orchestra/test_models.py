"""Tests for Orchestra models."""

from vibe3.orchestra.models import IssueInfo


def test_issue_info_slug():
    issue = IssueInfo(number=42, title="Fix login redirect bug", state=None)
    assert issue.slug == "fix-login-redirect-bug"


def test_issue_info_slug_special_chars():
    issue = IssueInfo(number=42, title="Add @mention support!!!", state=None)
    assert issue.slug == "add-mention-support"
