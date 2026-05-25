"""Tests for pr show command - local review integration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


@pytest.fixture
def mock_pr_for_local_review():
    """Create a mock PR for local review tests."""
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
    return mock_pr


@pytest.fixture
def mock_pr_svc_for_local_review(mock_pr_for_local_review):
    """Create a mock PR service for local review tests."""
    mock_pr_svc = MagicMock()
    mock_pr_svc.get_pr.return_value = mock_pr_for_local_review
    mock_pr_svc.git_client.get_current_branch.return_value = "feature/test"

    mock_github_client = MagicMock()
    mock_github_client.get_pr.return_value = mock_pr_for_local_review
    mock_pr_svc.github_client = mock_github_client

    return mock_pr_svc


class TestPRShowLocalReview:
    """Test pr show command with local review integration."""

    def test_pr_show_human_output_with_local_review(
        self, tmp_path: Path, mock_pr_svc_for_local_review
    ) -> None:
        """Test pr show displays local review in human-readable output."""
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

        mock_inspect_runner = MagicMock(return_value={})

        def side_effect_path(path_str: str) -> Path:
            if path_str == ".agent/reports/review":
                return reports_dir
            return Path(path_str)

        with patch(
            "vibe3.commands.pr_query.PRService",
            return_value=mock_pr_svc_for_local_review,
        ):
            with patch(
                "vibe3.analysis.inspect_query_service.build_change_analysis",
                side_effect=mock_inspect_runner,
            ):
                with patch(
                    "vibe3.analysis.local_review_report.Path",
                    side_effect=side_effect_path,
                ):
                    result = runner.invoke(app, ["pr", "show", "123"])

                    assert result.exit_code == 0
                    assert "### Local Review" in result.output
                    assert "Status: Found" in result.output
                    assert "Risk Level: HIGH" in result.output
                    assert "Risk Score: 7" in result.output
                    assert "Verdict: PASS" in result.output

    def test_pr_show_human_output_without_local_review(
        self, mock_pr_svc_for_local_review
    ) -> None:
        """Test pr show displays '无本地 review evidence' when no report exists."""
        mock_inspect_runner = MagicMock(return_value={})

        with patch(
            "vibe3.commands.pr_query.PRService",
            return_value=mock_pr_svc_for_local_review,
        ):
            with patch(
                "vibe3.analysis.inspect_query_service.build_change_analysis",
                side_effect=mock_inspect_runner,
            ):
                with patch(
                    "vibe3.analysis.local_review_report.Path.exists",
                    return_value=False,
                ):
                    result = runner.invoke(app, ["pr", "show", "123"])

                    assert result.exit_code == 0
                    assert "### Local Review" in result.output
                    assert "无本地 review evidence" in result.output

    def test_pr_show_json_output_with_local_review(
        self, tmp_path: Path, mock_pr_for_local_review
    ) -> None:
        """Test pr show includes local review in JSON output."""
        mock_pr_for_local_review.model_dump.return_value = {
            "number": 123,
            "title": "Test PR",
            "state": "OPEN",
            "draft": False,
            "head_branch": "feature/test",
            "base_branch": "main",
            "url": "https://github.com/test/test/pull/123",
        }

        reports_dir = tmp_path / ".agent" / "reports" / "review"
        reports_dir.mkdir(parents=True)

        report_file = reports_dir / "pre-push-review-20260320-225241.md"
        report_file.write_text("""---
risk_level: HIGH
risk_score: 7
verdict: PASS
---
""")

        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr_for_local_review
        mock_pr_svc.git_client.get_current_branch.return_value = "feature/test"

        mock_github_client = MagicMock()
        mock_github_client.get_pr.return_value = mock_pr_for_local_review
        mock_pr_svc.github_client = mock_github_client

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

                    assert result.exit_code == 0

                    output_data = json.loads(result.output)
                    assert "local_review" in output_data
                    assert output_data["local_review"]["risk_level"] == "HIGH"
                    assert output_data["local_review"]["risk_score"] == 7
                    assert output_data["local_review"]["verdict"] == "PASS"

    def test_pr_show_json_output_without_local_review(
        self, mock_pr_for_local_review
    ) -> None:
        """Test pr show JSON output without local review field when no report."""
        mock_pr_for_local_review.model_dump.return_value = {
            "number": 123,
            "title": "Test PR",
            "state": "OPEN",
            "draft": False,
            "head_branch": "feature/test",
            "base_branch": "main",
            "url": "https://github.com/test/test/pull/123",
        }

        mock_pr_svc = MagicMock()
        mock_pr_svc.get_pr.return_value = mock_pr_for_local_review
        mock_pr_svc.git_client.get_current_branch.return_value = "feature/test"

        mock_github_client = MagicMock()
        mock_github_client.get_pr.return_value = mock_pr_for_local_review
        mock_pr_svc.github_client = mock_github_client

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

                    assert result.exit_code == 0

                    output_data = json.loads(result.output)
                    assert "local_review" not in output_data
