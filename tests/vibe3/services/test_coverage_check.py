"""Tests for CoverageService coverage check."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.analysis.coverage_service import CoverageService
from vibe3.models.coverage import CoverageReport


def test_run_coverage_check_success(
    coverage_service: CoverageService,
    mock_project_root: Path,
    sample_coverage_data: dict,
) -> None:
    """Test run_coverage_check success."""
    coverage_service.project_root = mock_project_root

    mock_result = MagicMock()
    mock_result.stdout = "pytest output"
    mock_result.stderr = ""
    mock_result.returncode = 0

    def fake_subprocess_run(*args, **kwargs):
        cov_file = (
            mock_project_root / ".agent" / "reports" / "test-branch" / "coverage.json"
        )
        cov_file.parent.mkdir(parents=True, exist_ok=True)
        cov_file.write_text(json.dumps(sample_coverage_data))
        return mock_result

    with patch("vibe3.clients.git_client.GitClient") as mock_git:
        mock_git.return_value.get_current_branch.return_value = "test-branch"
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            report = coverage_service.run_coverage_check()

            assert isinstance(report, CoverageReport)
            assert report.total_covered == 2850
            assert report.total_lines == 3300
            assert report.overall_percent == pytest.approx(86.36, rel=0.01)
            assert report.all_passing is True
            assert len(report.get_failing_layers()) == 0


def test_run_coverage_check_with_failures(
    coverage_service: CoverageService,
    mock_project_root: Path,
) -> None:
    """Test run_coverage_check with coverage failures."""
    low_coverage_data = {
        "files": {
            "src/vibe3/services/pr_service.py": {
                "summary": {
                    "covered_lines": 500,
                    "num_statements": 1000,
                }
            },
            "src/vibe3/clients/github_client.py": {
                "summary": {
                    "covered_lines": 420,
                    "num_statements": 500,
                }
            },
            "src/vibe3/commands/pr_lifecycle.py": {
                "summary": {
                    "covered_lines": 900,
                    "num_statements": 1000,
                }
            },
        }
    }

    coverage_service.project_root = mock_project_root

    mock_result = MagicMock()
    mock_result.stdout = "pytest output"
    mock_result.stderr = ""
    mock_result.returncode = 0

    def fake_subprocess_run(*args, **kwargs):
        cov_file = (
            mock_project_root / ".agent" / "reports" / "test-branch" / "coverage.json"
        )
        cov_file.parent.mkdir(parents=True, exist_ok=True)
        cov_file.write_text(json.dumps(low_coverage_data))
        return mock_result

    with patch("vibe3.clients.git_client.GitClient") as mock_git:
        mock_git.return_value.get_current_branch.return_value = "test-branch"
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            report = coverage_service.run_coverage_check()

            assert report.all_passing is False

            failing = report.get_failing_layers()
            assert len(failing) == 1
            assert failing[0].layer_name == "services"
            assert failing[0].coverage_percent == 50.0
            assert failing[0].gap == 30.0


def test_run_coverage_check_empty_project(
    coverage_service: CoverageService,
    mock_project_root: Path,
) -> None:
    """Test run_coverage_check with empty project (no files)."""
    empty_data = {"files": {}}

    coverage_service.project_root = mock_project_root

    mock_result = MagicMock()
    mock_result.stdout = "pytest output"
    mock_result.stderr = ""
    mock_result.returncode = 0

    def fake_subprocess_run(*args, **kwargs):
        cov_file = (
            mock_project_root / ".agent" / "reports" / "test-branch" / "coverage.json"
        )
        cov_file.parent.mkdir(parents=True, exist_ok=True)
        cov_file.write_text(json.dumps(empty_data))
        return mock_result

    with patch("vibe3.clients.git_client.GitClient") as mock_git:
        mock_git.return_value.get_current_branch.return_value = "test-branch"
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            report = coverage_service.run_coverage_check()

            assert report.total_covered == 0
            assert report.total_lines == 0
            assert report.overall_percent == 0.0
            assert report.all_passing is False
