"""Tests for GitHub issue batch title fetching."""

from unittest.mock import MagicMock

from vibe3.clients.github_issues_ops import IssuesMixin


class TestIssuesBatchFetch:
    """Tests for batch issue fetching."""

    def test_batch_get_issues_success(self):
        """Test successful batch issue fetch."""
        mock_client = MagicMock(spec=IssuesMixin)
        mock_client.list_issues.return_value = [
            {"number": 123, "title": "Test Issue 123"},
            {"number": 456, "title": "Test Issue 456"},
        ]

        result = IssuesMixin.batch_get_issues(mock_client, [123, 456])

        assert result == {123: "Test Issue 123", 456: "Test Issue 456"}
        mock_client.list_issues.assert_called_once_with(
            limit=30,
            state="all",
            repo=None,
            search="#123 #456",
            fields=["number", "title"],
        )

    def test_batch_get_issues_includes_closed_issues_and_filters_results(self):
        """Batch issue fetch should include closed issues and filter search noise."""
        mock_client = MagicMock(spec=IssuesMixin)
        mock_client.list_issues.return_value = [
            {"number": 123, "title": "Requested Issue"},
            {"number": 999, "title": "Mentioned Issue"},
        ]

        result = IssuesMixin.batch_get_issues(mock_client, [123])

        assert result == {123: "Requested Issue"}
        mock_client.list_issues.assert_called_once_with(
            limit=30,
            state="all",
            repo=None,
            search="#123",
            fields=["number", "title"],
        )

    def test_batch_get_issues_empty_list(self):
        """Test batch get with empty issue list returns empty dict."""
        mock_client = MagicMock(spec=IssuesMixin)
        result = IssuesMixin.batch_get_issues(mock_client, [])
        assert result == {}

    def test_batch_get_issues_network_error(self):
        """Test batch get returns None on network error."""
        mock_client = MagicMock(spec=IssuesMixin)
        mock_client.list_issues.side_effect = RuntimeError("network error")

        result = IssuesMixin.batch_get_issues(mock_client, [123, 456])
        assert result is None
