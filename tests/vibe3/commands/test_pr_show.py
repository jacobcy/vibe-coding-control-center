"""Tests for pr show command."""

import json
from pathlib import Path
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

    def test_pr_show_comments_sorted_chronologically(self) -> None:
        """Test pr show displays comments in chronological order."""
        # Create a mock PR with comments in reverse chronological order
        mock_pr = MagicMock()
        mock_pr.number = 126
        mock_pr.title = "Test PR with comments"
        mock_pr.state.value = "OPEN"
        mock_pr.draft = False
        mock_pr.head_branch = "feature/test-comments"
        mock_pr.base_branch = "main"
        mock_pr.url = "https://github.com/test/test/pull/126"
        mock_pr.metadata = None
        mock_pr.body = "Test body"
        mock_pr.review_comments = []
        mock_pr.comments = [
            {
                "user": {"login": "charlie"},
                "body": "Latest comment",
                "createdAt": "2026-05-06T15:00:00Z",
            },
            {
                "user": {"login": "alice"},
                "body": "First comment",
                "createdAt": "2026-05-06T10:00:00Z",
            },
            {
                "user": {"login": "bob"},
                "body": "Second comment",
                "createdAt": "2026-05-06T12:00:00Z",
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
                result = runner.invoke(app, ["pr", "show", "126"])

                # Check command succeeded
                assert result.exit_code == 0

                # Check comments appear in chronological order (ascending)
                # Find positions of each comment in output
                alice_pos = result.output.find("First comment")
                bob_pos = result.output.find("Second comment")
                charlie_pos = result.output.find("Latest comment")

                # Verify chronological ordering
                # alice (10:00) < bob (12:00) < charlie (15:00)
                assert alice_pos < bob_pos < charlie_pos


class TestPRShowLocalReview:
    """Test pr show command with local review integration."""

    def test_pr_show_human_output_with_local_review(self, tmp_path: Path) -> None:
        """Test pr show displays local review in human-readable output."""
        # Create a mock PR
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.title = "Test PR"
        mock_pr.state.value = "OPEN"
        mock_pr.draft = False
        mock_pr.head_branch = "feature/test"
        mock_pr.base_branch = "main"
        mock_pr.url = "https://github.com/test/test/pull/123"
        mock_pr.metadata = None
        mock_pr.body = "Test body"
        mock_pr.review_comments = []
        mock_pr.comments = []

        # Create a local review report
        reports_dir = tmp_path / ".agent" / "reports" / "review"
        reports_dir.mkdir(parents=True)

        report_file = reports_dir / "pre-push-review-20260320-225241.md"
        report_file.write_text("""---
risk_level: HIGH
risk_score: 7
verdict: PASS
---

# Pre-push Review Report

## Risk Assessment
- Risk Level: HIGH
- Risk Score: 7
- Verdict: PASS
""")

        # Mock PR service and dependencies
        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = "feature/test"

        # Mock GitHub client to return PR
        mock_github_client = MagicMock()
        mock_github_client.get_pr.return_value = mock_pr
        mock_pr_svc.github_client = mock_github_client

        # Mock inspect runner
        mock_inspect_runner = MagicMock(return_value={})

        def side_effect_path(path_str: str) -> Path:
            if path_str == ".agent/reports/review":
                return reports_dir
            return Path(path_str)

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            with patch(
                "vibe3.analysis.inspect_query_service.build_change_analysis",
                side_effect=mock_inspect_runner,
            ):
                with patch(
                    "vibe3.analysis.local_review_report.Path",
                    side_effect=side_effect_path,
                ):
                    result = runner.invoke(app, ["pr", "show", "123"])

                    # Check command succeeded
                    assert result.exit_code == 0

                    # Check local review section appears in output
                    assert "### Local Review" in result.output
                    assert "Status: Found" in result.output
                    assert "Risk Level: HIGH" in result.output
                    assert "Risk Score: 7" in result.output
                    assert "Verdict: PASS" in result.output
                    # Report path should contain the filename
                    assert (
                        "pre-push-review-20260320-225241.md" in result.output
                        or ".agent/reports" in result.output
                    )

    def test_pr_show_human_output_without_local_review(self) -> None:
        """Test pr show displays '无本地 review evidence' when no report exists."""
        # Create a mock PR
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.title = "Test PR"
        mock_pr.state.value = "OPEN"
        mock_pr.draft = False
        mock_pr.head_branch = "feature/test"
        mock_pr.base_branch = "main"
        mock_pr.url = "https://github.com/test/test/pull/123"
        mock_pr.metadata = None
        mock_pr.body = "Test body"
        mock_pr.review_comments = []
        mock_pr.comments = []

        # Mock PR service
        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = "feature/test"

        mock_github_client = MagicMock()
        mock_github_client.get_pr.return_value = mock_pr
        mock_pr_svc.github_client = mock_github_client

        # Mock inspect runner
        mock_inspect_runner = MagicMock(return_value={})

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            with patch(
                "vibe3.analysis.inspect_query_service.build_change_analysis",
                side_effect=mock_inspect_runner,
            ):
                with patch(
                    "vibe3.analysis.local_review_report.Path.exists",
                    return_value=False,
                ):
                    result = runner.invoke(app, ["pr", "show", "123"])

                    # Check command succeeded
                    assert result.exit_code == 0

                    # Check local review section shows no evidence message
                    assert "### Local Review" in result.output
                    assert "无本地 review evidence" in result.output

    def test_pr_show_json_output_with_local_review(self, tmp_path: Path) -> None:
        """Test pr show includes local review in JSON output."""
        # Create a mock PR
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.title = "Test PR"
        mock_pr.state.value = "OPEN"
        mock_pr.draft = False
        mock_pr.head_branch = "feature/test"
        mock_pr.base_branch = "main"
        mock_pr.url = "https://github.com/test/test/pull/123"
        mock_pr.metadata = None
        mock_pr.body = "Test body"
        mock_pr.review_comments = []
        mock_pr.comments = []
        mock_pr.model_dump.return_value = {
            "number": 123,
            "title": "Test PR",
            "state": "OPEN",
            "draft": False,
            "head_branch": "feature/test",
            "base_branch": "main",
            "url": "https://github.com/test/test/pull/123",
        }

        # Create a local review report
        reports_dir = tmp_path / ".agent" / "reports" / "review"
        reports_dir.mkdir(parents=True)

        report_file = reports_dir / "pre-push-review-20260320-225241.md"
        report_file.write_text("""---
risk_level: HIGH
risk_score: 7
verdict: PASS
---
""")

        # Mock PR service
        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = "feature/test"

        mock_github_client = MagicMock()
        mock_github_client.get_pr.return_value = mock_pr
        mock_pr_svc.github_client = mock_github_client

        # Mock inspect runner
        mock_inspect_runner = MagicMock(return_value={})

        def side_effect_path(path_str: str) -> Path:
            if path_str == ".agent/reports/review":
                return reports_dir
            return Path(path_str)

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            with patch(
                "vibe3.analysis.inspect_query_service.build_change_analysis",
                side_effect=mock_inspect_runner,
            ):
                with patch(
                    "vibe3.analysis.local_review_report.Path",
                    side_effect=side_effect_path,
                ):
                    result = runner.invoke(app, ["pr", "show", "123", "--json"])

                    # Check command succeeded
                    assert result.exit_code == 0

                    # Parse JSON output
                    output_data = json.loads(result.output)

                    # Check local_review field exists
                    assert "local_review" in output_data
                    assert output_data["local_review"]["risk_level"] == "HIGH"
                    assert output_data["local_review"]["risk_score"] == 7
                    assert output_data["local_review"]["verdict"] == "PASS"
                    assert (
                        "pre-push-review-20260320-225241.md"
                        in output_data["local_review"]["report_path"]
                    )

    def test_pr_show_json_output_without_local_review(self) -> None:
        """Test pr show JSON output without local review field when no report."""
        # Create a mock PR
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.title = "Test PR"
        mock_pr.state.value = "OPEN"
        mock_pr.draft = False
        mock_pr.head_branch = "feature/test"
        mock_pr.base_branch = "main"
        mock_pr.url = "https://github.com/test/test/pull/123"
        mock_pr.metadata = None
        mock_pr.body = "Test body"
        mock_pr.review_comments = []
        mock_pr.comments = []
        mock_pr.model_dump.return_value = {
            "number": 123,
            "title": "Test PR",
            "state": "OPEN",
            "draft": False,
            "head_branch": "feature/test",
            "base_branch": "main",
            "url": "https://github.com/test/test/pull/123",
        }

        # Mock PR service
        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr
        mock_pr_svc.git_client.get_current_branch.return_value = "feature/test"

        mock_github_client = MagicMock()
        mock_github_client.get_pr.return_value = mock_pr
        mock_pr_svc.github_client = mock_github_client

        # Mock inspect runner
        mock_inspect_runner = MagicMock(return_value={})

        with patch("vibe3.commands.pr_query.PRService", return_value=mock_pr_svc):
            with patch(
                "vibe3.analysis.inspect_query_service.build_change_analysis",
                side_effect=mock_inspect_runner,
            ):
                with patch(
                    "vibe3.analysis.local_review_report.Path.exists",
                    return_value=False,
                ):
                    result = runner.invoke(app, ["pr", "show", "123", "--json"])

                    # Check command succeeded
                    assert result.exit_code == 0

                    # Parse JSON output
                    output_data = json.loads(result.output)

                    # Check local_review field does NOT exist when no report
                    assert "local_review" not in output_data
