"""Tests for pr show command - bound task display."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


@pytest.fixture
def mock_pr_svc_factory():
    """Factory fixture to create mock PR service with common setup."""

    def _factory(pr_number: int, head_branch: str, **kwargs) -> MagicMock:
        mock_pr = MagicMock()
        mock_pr.number = pr_number
        mock_pr.state.value = kwargs.get("state", "OPEN")
        mock_pr.draft = kwargs.get("draft", False)
        mock_pr.head_branch = head_branch
        mock_pr.base_branch = kwargs.get("base_branch", "main")
        mock_pr.url = f"https://github.com/test/test/pull/{pr_number}"
        mock_pr.metadata = kwargs.get("metadata", None)
        mock_pr.body = kwargs.get("body", "Test body")
        mock_pr.review_comments = kwargs.get("review_comments", [])
        mock_pr.comments = kwargs.get("comments", [])

        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = head_branch
        mock_pr_svc.github_client.get_pr.return_value = mock_pr

        mock_store = MagicMock()
        mock_store.get_issue_links.return_value = kwargs.get("issue_links", [])
        # Configure get_task_issue_number for fallback resolution
        # Default to None so issue_links is used first
        mock_store.get_task_issue_number.return_value = kwargs.get(
            "task_issue_number", None
        )
        mock_pr_svc.store = mock_store

        return mock_pr_svc

    return _factory


class TestPRShowBoundTask:
    """Test pr show command with bound task display."""

    def test_pr_show_renders_bound_tasks_from_flow(self, mock_pr_svc_factory) -> None:
        """Test pr show displays bound tasks from flow truth."""
        mock_pr_svc = mock_pr_svc_factory(
            pr_number=123,
            head_branch="task/issue-456",
            issue_links=[
                {"issue_number": 456, "issue_role": "task"},
                {"issue_number": 789, "issue_role": "task"},
                {"issue_number": 100, "issue_role": "related"},
            ],
        )

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            result = runner.invoke(app, ["pr", "show", "123"])

            assert result.exit_code == 0
            assert "### Bound Task(s)" in result.output
            assert "#456" in result.output
            assert "#789" in result.output

    def test_pr_show_no_bound_tasks_message(self, mock_pr_svc_factory) -> None:
        """Test pr show when no bound tasks exist in flow."""
        mock_pr_svc = mock_pr_svc_factory(
            pr_number=124,
            head_branch="feature/test",
            issue_links=[{"issue_number": 100, "issue_role": "related"}],
        )

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            result = runner.invoke(app, ["pr", "show", "124"])

            assert result.exit_code == 0
            assert "### Bound Task(s)" not in result.output

    def test_pr_show_renders_comments(self, mock_pr_svc_factory) -> None:
        """Test pr show displays PR comments with author and time."""
        mock_pr_svc = mock_pr_svc_factory(
            pr_number=125,
            head_branch="feature/test-comments",
            comments=[
                {
                    "user": {"login": "alice"},
                    "body": "Great work on this PR!",
                    "createdAt": "2026-05-06T10:30:00Z",
                },
                {
                    "user": {"login": "bob"},
                    "body": "Please add more tests.",
                    "createdAt": "2026-05-06T11:00:00Z",
                },
            ],
        )

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            result = runner.invoke(app, ["pr", "show", "125"])

            assert result.exit_code == 0
            assert "### General Comments" in result.output
            assert "alice" in result.output
            assert "bob" in result.output
            assert "2026-05-06 10:30" in result.output
