"""Tests for reports CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.commands.reports import app
from vibe3.services.report_cleanup_service import (
    ReportCleanupService,
    ReportInfo,
)


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture()
def mock_service() -> MagicMock:
    """Create mock ReportCleanupService."""
    return MagicMock(spec=ReportCleanupService)


@pytest.fixture()
def sample_reports() -> list[ReportInfo]:
    """Create sample report info for testing."""
    return [
        ReportInfo(
            path=Path(".agent/reports/pre-push-review-20240101.md"),
            size_bytes=1024,
            mtime=1704067200.0,
            age_days=30.0,
        ),
        ReportInfo(
            path=Path(".agent/reports/pre-push-review-20240102.md"),
            size_bytes=2048,
            mtime=1704153600.0,
            age_days=29.0,
        ),
    ]


# --- list command ---


def test_list_all_reports(
    cli_runner: CliRunner, mock_service: MagicMock, sample_reports: list[ReportInfo]
) -> None:
    """vibe3 reports list shows all reports."""
    from vibe3.services.report_cleanup_service import ReportTypeDefinition

    mock_service.get_report_types.return_value = [
        ReportTypeDefinition(
            name="pre-push-review", pattern="*.md", is_subdirectory=False
        ),
    ]
    mock_service.list_reports.return_value = sample_reports

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["list"])

    assert result.exit_code == 0
    assert "pre-push-review" in result.output


def test_list_specific_type(
    cli_runner: CliRunner, mock_service: MagicMock, sample_reports: list[ReportInfo]
) -> None:
    """vibe3 reports list --type shows specific type only."""
    mock_service.list_reports.return_value = sample_reports

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["list", "--type", "pre-push-review"])

    assert result.exit_code == 0
    mock_service.list_reports.assert_called_once_with("pre-push-review")


def test_list_json_output(
    cli_runner: CliRunner, mock_service: MagicMock, sample_reports: list[ReportInfo]
) -> None:
    """vibe3 reports list --json outputs JSON format."""
    mock_service.get_report_types.return_value = []
    mock_service.list_reports.return_value = []

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["list", "--json"])

    assert result.exit_code == 0
    # Should output JSON array
    assert "[" in result.output or result.output.strip() == "[]"


def test_list_empty_reports(cli_runner: CliRunner, mock_service: MagicMock) -> None:
    """vibe3 reports list handles empty results gracefully."""
    mock_service.list_reports.return_value = []

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["list", "--type", "pre-push-review"])

    assert result.exit_code == 0
    assert "No reports found" in result.output


# --- clean command ---


def test_clean_dry_run_default(cli_runner: CliRunner, mock_service: MagicMock) -> None:
    """vibe3 reports clean defaults to dry-run mode."""
    mock_service.clean_all.return_value = {
        "pre-push-review": {
            "kept": 5,
            "deleted": 2,
            "freed_bytes": 2048,
            "files_deleted": [],
        },
    }

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["clean"])

    assert result.exit_code == 0
    # Should call clean_all with dry_run=True
    mock_service.clean_all.assert_called_once_with(dry_run=True)
    assert "Would delete" in result.output


def test_clean_default_is_dry_run(cli_runner: CliRunner) -> None:
    """vibe3 reports clean defaults to dry-run mode (preview only)."""
    # Without --force, command runs in dry-run mode by default
    # This is the safety behavior: preview without deleting
    with patch("vibe3.commands.reports.ReportCleanupService") as mock_service_class:
        mock_service = MagicMock()
        mock_service_class.return_value = mock_service
        mock_service.clean_all.return_value = {
            "pre-push-review": {
                "kept": 5,
                "deleted": 2,
                "freed_bytes": 2048,
                "files_deleted": [],
            },
        }

        result = cli_runner.invoke(app, ["clean"])

        assert result.exit_code == 0
        # Should call clean_all with dry_run=True
        mock_service.clean_all.assert_called_once_with(dry_run=True)
        assert "Would delete" in result.output


def test_clean_with_force(cli_runner: CliRunner, mock_service: MagicMock) -> None:
    """vibe3 reports clean --force actually deletes."""
    mock_service.clean_all.return_value = {
        "pre-push-review": {
            "kept": 5,
            "deleted": 2,
            "freed_bytes": 2048,
            "files_deleted": [],
        },
    }

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["clean", "--force"])

    assert result.exit_code == 0
    # Should call clean_all with dry_run=False
    mock_service.clean_all.assert_called_once_with(dry_run=False)
    assert "Deleted" in result.output


def test_clean_specific_type(cli_runner: CliRunner, mock_service: MagicMock) -> None:
    """vibe3 reports clean --type cleans specific type only."""
    mock_service.clean_reports.return_value = {
        "kept": 5,
        "deleted": 2,
        "freed_bytes": 2048,
        "files_deleted": ["file1.md", "file2.md"],
    }

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(
            app, ["clean", "--type", "pre-push-review", "--force"]
        )

    assert result.exit_code == 0
    mock_service.clean_reports.assert_called_once_with(
        "pre-push-review", dry_run=False, max_count=None, max_age_days=None
    )


def test_clean_with_override_max_count(
    cli_runner: CliRunner, mock_service: MagicMock
) -> None:
    """vibe3 reports clean --max-count overrides retention."""
    mock_service.clean_reports.return_value = {
        "kept": 2,
        "deleted": 3,
        "freed_bytes": 3072,
        "files_deleted": [],
    }

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(
            app,
            ["clean", "--type", "pre-push-review", "--max-count", "2", "--force"],
        )

    assert result.exit_code == 0
    mock_service.clean_reports.assert_called_once_with(
        "pre-push-review", dry_run=False, max_count=2, max_age_days=None
    )


def test_clean_json_output(cli_runner: CliRunner, mock_service: MagicMock) -> None:
    """vibe3 reports clean --json outputs JSON format."""
    mock_service.clean_all.return_value = {
        "pre-push-review": {
            "kept": 5,
            "deleted": 2,
            "freed_bytes": 2048,
            "files_deleted": [],
        },
    }

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["clean", "--json"])

    assert result.exit_code == 0
    assert "{" in result.output


# --- status command ---


def test_status(cli_runner: CliRunner, mock_service: MagicMock) -> None:
    """vibe3 reports status shows disk usage."""
    mock_service.get_disk_usage.return_value = {
        "total_bytes": 10240,
        "total_files": 5,
        "total_dirs": 2,
    }
    mock_service.get_report_types.return_value = []
    mock_service.list_reports.return_value = []

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "Reports Directory Summary" in result.output
    assert "10.0 KB" in result.output


def test_status_json(cli_runner: CliRunner, mock_service: MagicMock) -> None:
    """vibe3 reports status --json outputs JSON format."""
    mock_service.get_disk_usage.return_value = {
        "total_bytes": 10240,
        "total_files": 5,
        "total_dirs": 2,
    }

    with patch(
        "vibe3.commands.reports.ReportCleanupService", return_value=mock_service
    ):
        result = cli_runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    assert "total_bytes" in result.output
    assert "10240" in result.output
