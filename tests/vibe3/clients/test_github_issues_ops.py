"""Tests for new IssuesMixin methods."""

import json
from unittest.mock import MagicMock, patch

from vibe3.clients.github_client import GitHubClient


def _client() -> GitHubClient:
    return GitHubClient()


# -- list_issues_with_assignees --


def test_list_issues_with_assignees_success():
    client = _client()
    payload = [{"number": 1, "title": "T", "labels": [], "assignees": [], "url": "u"}]
    mock_result = MagicMock(returncode=0, stdout=json.dumps(payload))
    with patch("subprocess.run", return_value=mock_result):
        result = client.list_issues_with_assignees(limit=10)
    assert len(result) == 1
    assert result[0]["number"] == 1


def test_list_issues_with_assignees_failure_returns_empty():
    client = _client()
    mock_result = MagicMock(returncode=1, stderr="auth error", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        result = client.list_issues_with_assignees()
    assert result == []


def test_list_issues_with_assignees_passes_repo():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="[]")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        client.list_issues_with_assignees(repo="owner/repo")
    cmd = mock_run.call_args[0][0]
    assert "--repo" in cmd
    assert "owner/repo" in cmd


# -- close_issue --


def test_close_issue_success():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result):
        assert client.close_issue(42) is True


def test_close_issue_with_comment():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        client.close_issue(42, comment="closing because done")
    cmd = mock_run.call_args[0][0]
    assert "--comment" in cmd


def test_close_issue_failure_returns_false():
    client = _client()
    mock_result = MagicMock(returncode=1, stderr="not found", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        assert client.close_issue(999) is False


# -- add_comment --


def test_add_comment_success():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result):
        assert client.add_comment(42, "hello") is True


def test_add_comment_failure_returns_false():
    client = _client()
    mock_result = MagicMock(returncode=1, stderr="error", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        assert client.add_comment(42, "hello") is False


def test_add_comment_passes_repo():
    client = _client()
    mock_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        client.add_comment(42, "hi", repo="owner/repo")
    cmd = mock_run.call_args[0][0]
    assert "--repo" in cmd


# -- get_pr_for_issue --


def test_get_pr_for_issue_found():
    client = _client()
    payload = [
        {
            "number": 10,
            "closingIssuesReferences": [{"number": 42}],
        }
    ]
    mock_result = MagicMock(returncode=0, stdout=json.dumps(payload))
    with patch("subprocess.run", return_value=mock_result):
        pr = client.get_pr_for_issue(42)
    assert pr == 10


def test_get_pr_for_issue_not_found():
    client = _client()
    payload = [{"number": 10, "closingIssuesReferences": [{"number": 99}]}]
    mock_result = MagicMock(returncode=0, stdout=json.dumps(payload))
    with patch("subprocess.run", return_value=mock_result):
        pr = client.get_pr_for_issue(42)
    assert pr is None


def test_get_pr_for_issue_gh_failure():
    client = _client()
    mock_result = MagicMock(returncode=1, stderr="error", stdout="")
    with patch("subprocess.run", return_value=mock_result):
        pr = client.get_pr_for_issue(42)
    assert pr is None
