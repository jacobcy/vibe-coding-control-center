"""Tests for GitHub client - Issues."""

import json
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients.github_client import GitHubClient


@pytest.fixture
def github_client() -> GitHubClient:
    """Create GitHub client fixture."""
    return GitHubClient()


@pytest.fixture
def mock_subprocess() -> MagicMock:
    """Mock subprocess.run."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock:
        yield mock


def _client() -> GitHubClient:
    return GitHubClient()


def test_list_issues_with_assignees_success():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "number": 1,
                        "title": "Test Issue",
                        "assignees": [{"login": "user1"}],
                        "labels": [{"name": "bug"}],
                    }
                ]
            ),
        )

        issues = client.list_issues_with_assignees()
        assert len(issues) == 1
        assert issues[0]["number"] == 1
        assert issues[0]["assignees"][0]["login"] == "user1"


def test_list_issues_with_assignees_failure_returns_empty():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Error")
        issues = client.list_issues_with_assignees()
        assert issues == []


def test_list_issues_with_assignees_passes_repo():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        client.list_issues_with_assignees(repo="org/repo")

        # Verify gh issue list was called with the correct repo
        found_repo = False
        for call in mock_run.call_args_list:
            args = call[0][0]
            if "--repo" in args and "org/repo" in args:
                found_repo = True
        assert found_repo


def test_close_issue_success():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert client.close_issue(1) is True
        # Verify gh issue close was called with correct arguments
        args = mock_run.call_args[0][0]
        assert args[:4] == ["gh", "issue", "close", "1"]


def test_remove_assignees_success():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert client.remove_assignees(1, ["alice", "bob"]) is True

        args = mock_run.call_args[0][0]
        assert "--remove-assignee" in args
        assert "alice" in args
        assert "bob" in args


def test_remove_assignees_empty_is_noop():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        assert client.remove_assignees(1, []) is True
        mock_run.assert_not_called()


def test_close_issue_with_comment():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert client.close_issue(1, comment="Fixed it") is True


def test_close_issue_failure_returns_false():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert client.close_issue(1) is False
        # Verify gh issue close was still called
        args = mock_run.call_args[0][0]
        assert args[:4] == ["gh", "issue", "close", "1"]


def test_add_comment_success():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert client.add_comment(1, "Nice") is True
        # Verify gh issue comment was called with correct arguments
        args = mock_run.call_args[0][0]
        assert args[:4] == ["gh", "issue", "comment", "1"]
        assert "--body" in args
        assert "Nice" in args


def test_add_comment_failure_returns_false():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        assert client.add_comment(1, "Nice") is False
        # Verify gh issue comment was still called
        args = mock_run.call_args[0][0]
        assert args[:4] == ["gh", "issue", "comment", "1"]


def test_add_comment_passes_repo():
    client = _client()
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        client.add_comment(1, "Nice", repo="org/repo")

        # Verify gh issue comment was called with the correct repo
        found_repo = False
        for call in mock_run.call_args_list:
            args = call[0][0]
            if "--repo" in args and "org/repo" in args:
                found_repo = True
        assert found_repo


def test_close_issue_if_open_already_closed(github_client: GitHubClient) -> None:
    """Issue already closed should return 'already_closed' without calling close."""
    with (
        patch.object(
            github_client, "view_issue", return_value={"state": "closed"}
        ) as mock_view,
        patch.object(github_client, "close_issue") as mock_close,
    ):
        result = github_client.close_issue_if_open(issue_number=123)

        mock_view.assert_called_once_with(123, repo=None, fields=["state"])
        mock_close.assert_not_called()
        assert result == "already_closed"


def test_close_issue_if_open_calls_close_once(github_client: GitHubClient) -> None:
    """Open issue should call close_issue once and return 'closed'."""
    with (
        patch.object(
            github_client, "view_issue", return_value={"state": "open"}
        ) as mock_view,
        patch.object(github_client, "close_issue", return_value=True) as mock_close,
    ):
        result = github_client.close_issue_if_open(
            issue_number=123, closing_comment="Task not suitable"
        )

        mock_view.assert_called_once_with(123, repo=None, fields=["state"])
        mock_close.assert_called_once_with(
            issue_number=123, comment="Task not suitable", repo=None
        )
        assert result == "closed"


def test_close_issue_if_open_returns_failure_when_close_fails(
    github_client: GitHubClient,
) -> None:
    """Failed close operation should return 'failed'."""
    with (
        patch.object(
            github_client, "view_issue", return_value={"state": "open"}
        ) as mock_view,
        patch.object(github_client, "close_issue", return_value=False),
    ):
        result = github_client.close_issue_if_open(issue_number=123)

        mock_view.assert_called_once_with(123, repo=None, fields=["state"])
        assert result == "failed"


def test_view_issue_with_custom_fields(github_client: GitHubClient) -> None:
    """view_issue should use custom fields when provided."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"number": 123, "title": "Test Issue"}),
        )

        result = github_client.view_issue(issue_number=123, fields=["number", "title"])

        assert result == {"number": 123, "title": "Test Issue"}
        # Verify the --json argument uses the custom fields
        call_args = mock_run.call_args[0][0]
        assert "--json" in call_args
        json_index = call_args.index("--json")
        assert call_args[json_index + 1] == "number,title"


def test_view_issue_with_default_fields(github_client: GitHubClient) -> None:
    """view_issue should use default fields when fields parameter is None."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                {
                    "number": 123,
                    "title": "Test Issue",
                    "body": "Test body",
                    "state": "open",
                }
            ),
        )

        result = github_client.view_issue(issue_number=123)

        assert result["number"] == 123
        # Verify the --json argument uses the default fields (excluding comments)
        call_args = mock_run.call_args[0][0]
        assert "--json" in call_args
        json_index = call_args.index("--json")
        assert (
            call_args[json_index + 1]
            == "number,title,state,updatedAt,labels,assignees,milestone,body,url"
        )


def test_create_issue_success(github_client: GitHubClient) -> None:
    """create_issue should return issue number on success."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        # Mock gh issue create output
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/42\n",
        )

        result = github_client.create_issue(
            title="Test Issue",
            body="Test body",
        )

        assert result == 42
        # Verify gh issue create was called with correct arguments
        args = mock_run.call_args[0][0]
        assert args[:3] == ["gh", "issue", "create"]
        assert "--title" in args
        assert "Test Issue" in args
        assert "--body" in args
        assert "Test body" in args


def test_create_issue_with_labels(github_client: GitHubClient) -> None:
    """create_issue should apply labels when provided."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/43\n",
        )

        result = github_client.create_issue(
            title="Labeled Issue",
            body="Body",
            labels=["bug", "state/ready"],
        )

        assert result == 43
        args = mock_run.call_args[0][0]
        assert "--label" in args
        assert "bug" in args
        assert "state/ready" in args


def test_create_issue_with_assignees(github_client: GitHubClient) -> None:
    """create_issue should assign users when assignees provided."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="https://github.com/owner/repo/issues/44\n",
        )

        result = github_client.create_issue(
            title="Assigned Issue",
            body="Body",
            assignees=["user1", "user2"],
        )

        assert result == 44
        args = mock_run.call_args[0][0]
        assert "--assignee" in args
        assert "user1" in args
        assert "user2" in args


def test_create_issue_failure_returns_none(github_client: GitHubClient) -> None:
    """create_issue should return None on failure."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Validation Failed",
        )

        result = github_client.create_issue(
            title="Invalid Issue",
            body="Body",
        )

        assert result is None


def test_list_issue_comments_success(github_client: GitHubClient) -> None:
    """list_issue_comments should return comments on success."""
    with patch.object(github_client, "view_issue") as mock_view:
        mock_view.return_value = {
            "comments": [
                {
                    "id": 1,
                    "body": "First comment",
                    "author": {"login": "user1"},
                },
                {
                    "id": 2,
                    "body": "Second comment",
                    "author": {"login": "user2"},
                },
            ]
        }

        result = github_client.list_issue_comments(issue_number=123)

        mock_view.assert_called_once_with(123, repo=None, fields=["comments"])

        assert len(result) == 2
        assert result[0]["body"] == "First comment"
        assert result[1]["body"] == "Second comment"


def test_list_issue_comments_empty(github_client: GitHubClient) -> None:
    """list_issue_comments should return empty list when no comments."""
    with patch.object(github_client, "view_issue") as mock_view:
        mock_view.return_value = {"comments": []}

        result = github_client.list_issue_comments(issue_number=123)

        assert result == []


def test_list_issue_comments_timeout(github_client: GitHubClient) -> None:
    """list_issue_comments should return empty list on network error.

    view_issue returns "network_error" sentinel for network/auth failures.
    """
    with patch.object(github_client, "view_issue") as mock_view:
        mock_view.return_value = "network_error"

        result = github_client.list_issue_comments(issue_number=123)

        assert result == []


def test_list_issue_comments_failure(github_client: GitHubClient) -> None:
    """list_issue_comments should return empty list when issue not found.

    view_issue returns None for missing/inaccessible issues.
    """
    with patch.object(github_client, "view_issue") as mock_view:
        mock_view.return_value = None

        result = github_client.list_issue_comments(issue_number=999)

        assert result == []


def test_list_issues_default_fields_excludes_body(github_client: GitHubClient) -> None:
    """list_issues should exclude body field by default."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 1, "title": "Test"}]),
        )

        github_client.list_issues()

        args = mock_run.call_args[0][0]
        json_arg = args[args.index("--json") + 1]
        assert "body" not in json_arg
        assert "number" in json_arg
        assert "title" in json_arg


def test_list_issues_custom_fields(github_client: GitHubClient) -> None:
    """list_issues should use custom fields when provided."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 1, "title": "Test"}]),
        )

        github_client.list_issues(fields=["number", "title"])

        args = mock_run.call_args[0][0]
        json_arg = args[args.index("--json") + 1]
        assert json_arg == "number,title"


def test_list_issues_default_fields_backward_compat(
    github_client: GitHubClient,
) -> None:
    """list_issues default fields should return expected shape."""
    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "number": 1,
                        "title": "Test Issue",
                        "state": "open",
                        "updatedAt": "2024-01-01T00:00:00Z",
                        "labels": [{"name": "bug"}],
                        "assignees": [{"login": "user1"}],
                        "milestone": {"title": "v1.0"},
                    }
                ]
            ),
        )

        issues = github_client.list_issues()

        assert len(issues) == 1
        assert issues[0]["number"] == 1
        assert issues[0]["title"] == "Test Issue"
        assert issues[0]["state"] == "open"
        assert "labels" in issues[0]
        assert "assignees" in issues[0]
        assert "milestone" in issues[0]


# Tests for error classification and error_recorder callback


def test_classify_github_api_error_rate_limit() -> None:
    """Should classify rate limit errors correctly."""
    from vibe3.clients.github_issues_ops import _classify_github_api_error

    assert _classify_github_api_error("rate limit exceeded", 1) == "E_API_RATE_LIMIT"
    assert _classify_github_api_error("API rate_limit hit", 1) == "E_API_RATE_LIMIT"


def test_classify_github_api_error_timeout() -> None:
    """Should classify timeout errors correctly."""
    from vibe3.clients.github_issues_ops import _classify_github_api_error

    assert _classify_github_api_error("connection timeout", 1) == "E_API_TIMEOUT"
    assert _classify_github_api_error("request timed out", 1) == "E_API_TIMEOUT"


def test_classify_github_api_error_unavailable() -> None:
    """Should classify service unavailable errors correctly."""
    from vibe3.clients.github_issues_ops import _classify_github_api_error

    assert _classify_github_api_error("service unavailable", 1) == "E_API_UNAVAILABLE"
    assert (
        _classify_github_api_error("GitHub API unavailable", 1) == "E_API_UNAVAILABLE"
    )


def test_classify_github_api_error_network() -> None:
    """Should classify network errors correctly."""
    from vibe3.clients.github_issues_ops import _classify_github_api_error

    assert _classify_github_api_error("connection refused", 1) == "E_API_NETWORK"
    assert _classify_github_api_error("DNS resolution failed", 1) == "E_API_NETWORK"
    assert _classify_github_api_error("network error", 1) == "E_API_NETWORK"


def test_classify_github_api_error_unknown() -> None:
    """Should fallback to E_API_UNKNOWN for unclassified errors."""
    from vibe3.clients.github_issues_ops import _classify_github_api_error

    assert _classify_github_api_error("random error", 1) == "E_API_UNKNOWN"
    assert _classify_github_api_error("", 1) == "E_API_UNKNOWN"


def test_list_merged_prs_calls_error_recorder_on_failure(
    github_client: GitHubClient,
) -> None:
    """Should call error_recorder callback when API fails."""
    from unittest.mock import Mock

    mock_recorder = Mock(return_value=(False, 1))

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="rate limit exceeded")

        result = github_client.list_merged_prs(error_recorder=mock_recorder)

        assert result == []
        assert mock_recorder.called
        call_kwargs = mock_recorder.call_args[1]
        assert call_kwargs["error_code"] == "E_API_RATE_LIMIT"
        assert "Failed to list merged PRs" in call_kwargs["error_message"]


def test_list_issues_calls_error_recorder_on_failure(
    github_client: GitHubClient,
) -> None:
    """Should call error_recorder callback when API fails."""
    from unittest.mock import Mock

    mock_recorder = Mock(return_value=(False, 1))

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="connection timeout")

        result = github_client.list_issues(error_recorder=mock_recorder)

        assert result == []
        assert mock_recorder.called
        call_kwargs = mock_recorder.call_args[1]
        assert call_kwargs["error_code"] == "E_API_TIMEOUT"
        assert "Failed to list issues" in call_kwargs["error_message"]


def test_error_recorder_not_called_on_success(github_client: GitHubClient) -> None:
    """Should not call error_recorder when API succeeds."""
    from unittest.mock import Mock

    mock_recorder = Mock(return_value=(False, 1))

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps([{"number": 1, "title": "Test"}])
        )

        github_client.list_issues(error_recorder=mock_recorder)

        assert not mock_recorder.called


def test_error_recorder_exception_suppressed(github_client: GitHubClient) -> None:
    """Should suppress exceptions from error_recorder callback."""
    from unittest.mock import Mock

    mock_recorder = Mock(side_effect=RuntimeError("DB connection failed"))

    with patch("vibe3.clients.github_client_base.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="API error")

        # Should not raise, just log warning
        result = github_client.list_issues(error_recorder=mock_recorder)

        assert result == []
        assert mock_recorder.called
