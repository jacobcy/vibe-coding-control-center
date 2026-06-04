"""Tests for GitHub batch issues mixin."""

from unittest.mock import MagicMock, patch

from vibe3.clients.github_batch_issues_mixin import BatchIssuesMixin


class TestBatchIssuesMixin:
    """Tests for batch issue fetching."""

    def test_batch_get_issues_success(self):
        """Test successful batch issue fetch."""
        mock_client = MagicMock(spec=BatchIssuesMixin)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=(
                    '[{"number": 123, "title": "Test Issue 123"}, '
                    '{"number": 456, "title": "Test Issue 456"}]\n'
                ),
            )

            result = BatchIssuesMixin.batch_get_issues(mock_client, [123, 456])

            assert result == {123: "Test Issue 123", 456: "Test Issue 456"}

    def test_batch_get_issues_empty_list(self):
        """Test batch get with empty issue list returns empty dict."""
        mock_client = MagicMock(spec=BatchIssuesMixin)
        result = BatchIssuesMixin.batch_get_issues(mock_client, [])
        assert result == {}

    def test_batch_get_issues_network_error(self):
        """Test batch get returns None on network error."""
        mock_client = MagicMock(spec=BatchIssuesMixin)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="network error")

            result = BatchIssuesMixin.batch_get_issues(mock_client, [123, 456])
            assert result is None
