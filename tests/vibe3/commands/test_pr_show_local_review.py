"""Integration tests for pr show command with local review."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


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
