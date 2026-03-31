"""Tests for Orchestra models."""

from vibe3.models.orchestration import IssueInfo, IssueState


def test_issue_info_slug():
    issue = IssueInfo(number=42, title="Fix login redirect bug")
    assert issue.slug == "fix-login-redirect-bug"


def test_issue_info_slug_special_chars():
    issue = IssueInfo(number=42, title="Add @mention support!!!")
    assert issue.slug == "add-mention-support"


def test_issue_info_state_defaults_to_none():
    issue = IssueInfo(number=42, title="Test")
    assert issue.state is None


def test_from_github_payload_basic():
    payload = {
        "number": 88,
        "title": "Fix auth bug",
        "labels": [{"name": "bug"}, {"name": "priority/high"}],
        "assignees": [{"login": "alice"}, {"login": "bob"}],
        "html_url": "https://github.com/org/repo/issues/88",
    }
    issue = IssueInfo.from_github_payload(payload)
    assert issue is not None
    assert issue.number == 88
    assert issue.title == "Fix auth bug"
    assert issue.labels == ["bug", "priority/high"]
    assert issue.assignees == ["alice", "bob"]
    assert issue.url == "https://github.com/org/repo/issues/88"


def test_from_github_payload_derives_state_from_labels():
    payload = {
        "number": 42,
        "title": "Feature X",
        "labels": [{"name": "enhancement"}, {"name": "state/claimed"}],
        "assignees": [],
    }
    issue = IssueInfo.from_github_payload(payload)
    assert issue is not None
    assert issue.state == IssueState.CLAIMED


def test_from_github_payload_no_state_label():
    payload = {
        "number": 42,
        "title": "Feature X",
        "labels": [{"name": "bug"}, {"name": "priority/low"}],
        "assignees": [],
    }
    issue = IssueInfo.from_github_payload(payload)
    assert issue is not None
    assert issue.state is None


def test_from_github_payload_returns_none_on_invalid():
    assert IssueInfo.from_github_payload({}) is None
    assert IssueInfo.from_github_payload({"number": "not-int"}) is None
