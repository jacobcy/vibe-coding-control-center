"""Tests for pr show command with bound task display."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


class TestPRShowBoundTask:
    """Test pr show command with bound task display."""

    def test_pr_show_renders_bound_tasks_from_flow(self) -> None:
        """Test pr show displays bound tasks from flow truth."""
        # Create a mock PR
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.title = "Test PR with bound task"
        mock_pr.state.value = "OPEN"
        mock_pr.draft = False
        mock_pr.head_branch = "task/issue-456"
        mock_pr.base_branch = "main"
        mock_pr.url = "https://github.com/test/test/pull/123"
        mock_pr.metadata = None
        mock_pr.body = "Test body"
        mock_pr.review_comments = []
        mock_pr.comments = []

        # Mock PR service
        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = "task/issue-456"
        mock_pr_svc.github_client.get_pr.return_value = mock_pr

        # Mock SQLite client to return task issue links
        mock_store = MagicMock()
        mock_store.get_issue_links.return_value = [
            {"issue_number": 456, "issue_role": "task"},
            {"issue_number": 789, "issue_role": "task"},
            {"issue_number": 100, "issue_role": "related"},
        ]
        mock_pr_svc.store = mock_store

        with patch("vibe3.commands.pr_query.PRService") as mock_pr_service:
            mock_pr_service.return_value = mock_pr_svc
            with patch(
                "vibe3.commands.pr_query._load_pr_analysis_summary",
                return_value={},
            ):
                result = runner.invoke(app, ["pr", "show", "123"])

                # Check command succeeded
                assert result.exit_code == 0

                # Check bound tasks section appears in output
                assert "### Bound Task(s)" in result.output
                assert "#456" in result.output
                assert "#789" in result.output
                # Related issue should not appear in bound tasks
                assert "#100" not in result.output or "Bound Task" not in result.output

    def test_pr_show_no_bound_tasks_message(self) -> None:
        """Test pr show when no bound tasks exist in flow."""
        # Create a mock PR
        mock_pr = MagicMock()
        mock_pr.number = 124
        mock_pr.title = "Test PR without bound task"
        mock_pr.state.value = "OPEN"
        mock_pr.draft = False
        mock_pr.head_branch = "feature/test"
        mock_pr.base_branch = "main"
        mock_pr.url = "https://github.com/test/test/pull/124"
        mock_pr.metadata = None
        mock_pr.body = "Test body"
        mock_pr.review_comments = []
        mock_pr.comments = []

        # Mock PR service
        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = "feature/test"
        mock_pr_svc.github_client.get_pr.return_value = mock_pr

        # Mock SQLite client to return no task issue links
        mock_store = MagicMock()
        mock_store.get_issue_links.return_value = [
            {"issue_number": 100, "issue_role": "related"},
        ]
        mock_pr_svc.store = mock_store

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            with patch(
                "vibe3.commands.pr_query._load_pr_analysis_summary",
                return_value={},
            ):
                result = runner.invoke(app, ["pr", "show", "124"])

                # Check command succeeded
                assert result.exit_code == 0

                # Bound tasks section should NOT appear
                assert "### Bound Task(s)" not in result.output

    def test_pr_show_renders_comments(self) -> None:
        """Test pr show displays PR comments with author and time."""
        # Create a mock PR with comments
        mock_pr = MagicMock()
        mock_pr.number = 125
        mock_pr.title = "Test PR with comments"
        mock_pr.state.value = "OPEN"
        mock_pr.draft = False
        mock_pr.head_branch = "feature/test-comments"
        mock_pr.base_branch = "main"
        mock_pr.url = "https://github.com/test/test/pull/125"
        mock_pr.metadata = None
        mock_pr.body = "Test body"
        mock_pr.review_comments = []
        mock_pr.comments = [
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
        ]

        # Mock PR service
        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = "feature/test-comments"
        mock_pr_svc.github_client.get_pr.return_value = mock_pr

        # Mock SQLite client
        mock_store = MagicMock()
        mock_store.get_issue_links.return_value = []
        mock_pr_svc.store = mock_store

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            with patch(
                "vibe3.commands.pr_query._load_pr_analysis_summary",
                return_value={},
            ):
                result = runner.invoke(app, ["pr", "show", "125"])

                # Check command succeeded
                assert result.exit_code == 0

                # Check comments section appears
                assert "### General Comments" in result.output
                # Check author and time display
                assert "alice" in result.output
                assert "bob" in result.output
                assert "2026-05-06 10:30" in result.output
                # Check comment body
                assert "Great work on this PR!" in result.output
                assert "Please add more tests." in result.output
