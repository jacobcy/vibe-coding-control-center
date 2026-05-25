"""Tests for pr show command - comment and review sorting."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


@pytest.fixture
def mock_pr_svc_for_sorting():
    """Factory fixture to create mock PR service for sorting tests."""

    def _factory(pr_number: int, **kwargs) -> MagicMock:
        mock_pr = MagicMock()
        mock_pr.number = pr_number
        mock_pr.title = kwargs.get("title", "Test PR")
        mock_pr.state.value = kwargs.get("state", "OPEN")
        mock_pr.draft = kwargs.get("draft", False)
        mock_pr.head_branch = kwargs.get("head_branch", "feature/test")
        mock_pr.base_branch = kwargs.get("base_branch", "main")
        mock_pr.url = f"https://github.com/test/test/pull/{pr_number}"
        mock_pr.metadata = kwargs.get("metadata", None)
        mock_pr.body = kwargs.get("body", "")
        mock_pr.comments = kwargs.get("comments", [])
        mock_pr.review_comments = kwargs.get("review_comments", [])
        mock_pr.reviews = kwargs.get("reviews", [])

        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = kwargs.get(
            "head_branch", "feature/test"
        )
        mock_pr_svc.github_client.get_pr.return_value = mock_pr

        mock_store = MagicMock()
        mock_store.get_issue_links.return_value = []
        mock_pr_svc.store = mock_store

        return mock_pr_svc

    return _factory


def _invoke_pr_show(pr_number: int, mock_pr_svc: MagicMock):
    """Invoke pr show command with standard patches."""
    with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
        with patch(
            "vibe3.commands.pr_query._load_pr_analysis_summary",
            return_value={},
        ):
            return runner.invoke(app, ["pr", "show", str(pr_number)])


class TestPRShowCommentSorting:
    """Test pr show command chronological sorting of comments and reviews."""

    def test_comments_sorted_chronologically(self, mock_pr_svc_for_sorting) -> None:
        """General comments are sorted by createdAt ascending."""
        mock_pr_svc = mock_pr_svc_for_sorting(
            pr_number=126,
            comments=[
                {
                    "user": {"login": "c"},
                    "body": "LATE",
                    "createdAt": "2026-05-06T15:00:00Z",
                },
                {
                    "user": {"login": "a"},
                    "body": "EARLY",
                    "createdAt": "2026-05-06T10:00:00Z",
                },
                {
                    "user": {"login": "b"},
                    "body": "MID",
                    "createdAt": "2026-05-06T12:00:00Z",
                },
            ],
        )

        result = _invoke_pr_show(126, mock_pr_svc)

        assert result.exit_code == 0
        assert result.output.find("EARLY") < result.output.find("MID")
        assert result.output.find("MID") < result.output.find("LATE")

    def test_review_comments_sorted_chronologically(
        self, mock_pr_svc_for_sorting
    ) -> None:
        """Review comments are sorted by created_at ascending."""
        mock_pr_svc = mock_pr_svc_for_sorting(
            pr_number=127,
            title="Test PR with review comments",
            review_comments=[
                {
                    "user": {"login": "reviewer_c"},
                    "body": "LATE",
                    "path": "src/main.py",
                    "line": 42,
                    "created_at": "2026-05-06T15:00:00Z",
                },
                {
                    "user": {"login": "reviewer_a"},
                    "body": "EARLY",
                    "path": "src/utils.py",
                    "line": 10,
                    "created_at": "2026-05-06T10:00:00Z",
                },
                {
                    "user": {"login": "reviewer_b"},
                    "body": "MID",
                    "path": "tests/test_main.py",
                    "line": 25,
                    "created_at": "2026-05-06T12:00:00Z",
                },
            ],
        )

        result = _invoke_pr_show(127, mock_pr_svc)

        assert result.exit_code == 0
        assert "### Review Comments" in result.output
        assert result.output.find("EARLY") < result.output.find("MID")
        assert result.output.find("MID") < result.output.find("LATE")
        assert "src/utils.py:10" in result.output

    def test_reviews_sorted_chronologically(self, mock_pr_svc_for_sorting) -> None:
        """Reviews are sorted by submitted_at ascending."""
        mock_pr_svc = mock_pr_svc_for_sorting(
            pr_number=128,
            title="Test PR with reviews",
            reviews=[
                {
                    "user": {"login": "reviewer_c"},
                    "body": "Approved late",
                    "state": "APPROVED",
                    "submitted_at": "2026-05-06T15:00:00Z",
                },
                {
                    "user": {"login": "reviewer_a"},
                    "body": "Changes requested early",
                    "state": "CHANGES_REQUESTED",
                    "submitted_at": "2026-05-06T10:00:00Z",
                },
                {
                    "user": {"login": "reviewer_b"},
                    "body": "Commented mid",
                    "state": "COMMENTED",
                    "submitted_at": "2026-05-06T12:00:00Z",
                },
            ],
        )

        result = _invoke_pr_show(128, mock_pr_svc)

        assert result.exit_code == 0
        assert "### Reviews" in result.output
        assert (
            result.output.find("Changes requested early")
            < result.output.find("Commented mid")
            < result.output.find("Approved late")
        )

    def test_none_timestamp_does_not_crash(self, mock_pr_svc_for_sorting) -> None:
        """None timestamps in comments/reviews do not crash the command."""
        mock_pr_svc = mock_pr_svc_for_sorting(
            pr_number=129,
            title="Test PR with None timestamps",
            comments=[
                {
                    "user": {"login": "user_a"},
                    "body": "Valid timestamp",
                    "createdAt": "2026-05-06T10:00:00Z",
                },
                {
                    "user": {"login": "user_b"},
                    "body": "None timestamp",
                    "createdAt": None,
                },
            ],
            review_comments=[
                {
                    "user": {"login": "reviewer_a"},
                    "body": "Valid review comment",
                    "path": "src/main.py",
                    "line": 1,
                    "created_at": "2026-05-06T10:00:00Z",
                },
                {
                    "user": {"login": "reviewer_b"},
                    "body": "None review comment",
                    "path": "src/utils.py",
                    "line": 2,
                    "created_at": None,
                },
            ],
            reviews=[
                {
                    "user": {"login": "reviewer_c"},
                    "body": "Valid review",
                    "state": "APPROVED",
                    "submitted_at": "2026-05-06T10:00:00Z",
                },
                {
                    "user": {"login": "reviewer_d"},
                    "body": "None review",
                    "state": "COMMENTED",
                    "submitted_at": None,
                },
            ],
        )

        result = _invoke_pr_show(129, mock_pr_svc)

        assert result.exit_code == 0
        assert "### General Comments" in result.output
        assert "### Review Comments" in result.output
        assert "### Reviews" in result.output
        assert "Valid timestamp" in result.output
        assert "None timestamp" in result.output
