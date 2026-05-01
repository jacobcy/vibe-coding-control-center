"""Tests for ReportCleanupService."""

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.config.settings import (
    ReportsConfig,
    ReportsRetentionConfig,
    ReportsRetentionTypeConfig,
    VibeConfig,
)
from vibe3.services.report_cleanup_service import (
    ReportCleanupService,
    ReportInfo,
)


@pytest.fixture()
def reports_dir(tmp_path: Path) -> Path:
    """Create temporary reports directory."""
    reports = tmp_path / ".agent" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports


@pytest.fixture()
def config() -> VibeConfig:
    """Create test config with retention policy."""
    return VibeConfig(
        reports=ReportsConfig(
            retention=ReportsRetentionConfig(
                max_count=10,
                max_age_days=30,
                types={
                    "pre-push-review": ReportsRetentionTypeConfig(max_count=5),
                    "skills-state": ReportsRetentionTypeConfig(max_count=3),
                    "coverage": ReportsRetentionTypeConfig(max_count=3),
                },
            )
        )
    )


@pytest.fixture()
def service(reports_dir: Path, config: VibeConfig) -> ReportCleanupService:
    """Create service with test config."""
    service = ReportCleanupService(config=config)
    service.reports_dir = reports_dir
    return service


def test_get_report_types(service: ReportCleanupService) -> None:
    """get_report_types returns all defined types."""
    types = service.get_report_types()
    assert len(types) == 7
    type_names = [t.name for t in types]
    assert "pre-push-review" in type_names
    assert "coverage" in type_names
    assert "audit-result" in type_names


def test_list_reports_empty_directory(service: ReportCleanupService) -> None:
    """list_reports returns empty list when no reports exist."""
    reports = service.list_reports("pre-push-review")
    assert reports == []


def test_list_reports_flat_reports(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """list_reports finds reports in flat directory."""
    # Create test reports
    report1 = reports_dir / "pre-push-review-20240101.md"
    report2 = reports_dir / "pre-push-review-20240102.md"
    report1.write_text("report 1")
    report2.write_text("report 2")

    reports = service.list_reports("pre-push-review")
    assert len(reports) == 2
    assert all(isinstance(r, ReportInfo) for r in reports)
    # Should be sorted by mtime (newest first)
    assert reports[0].path.name == "pre-push-review-20240102.md"


def test_list_reports_subdirectory_reports(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """list_reports finds reports in subdirectories."""
    # Create coverage reports in flow subdirectories
    flow1_dir = reports_dir / "task-issue-123"
    flow1_dir.mkdir()
    coverage1 = flow1_dir / "coverage.json"
    coverage1.write_text('{"coverage": 80}')

    flow2_dir = reports_dir / "task-issue-456"
    flow2_dir.mkdir()
    coverage2 = flow2_dir / "coverage.json"
    coverage2.write_text('{"coverage": 85}')

    reports = service.list_reports("coverage")
    assert len(reports) == 2
    assert all(r.path.name == "coverage.json" for r in reports)


def test_clean_reports_dry_run(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """clean_reports in dry_run mode previews without deleting."""
    # Create 7 reports (exceeds max_count=5)
    for i in range(7):
        report = reports_dir / f"pre-push-review-2024010{i}.md"
        report.write_text(f"report {i}")
        # Small delay to ensure different mtimes
        time.sleep(0.01)

    result = service.clean_reports("pre-push-review", dry_run=True)

    # Should preview deletion
    assert result["kept"] == 5
    assert result["deleted"] == 2
    assert len(result["files_deleted"]) == 2
    # But files should still exist
    assert len(list(reports_dir.glob("pre-push-review-*.md"))) == 7


def test_clean_reports_actual_delete(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """clean_reports with dry_run=False deletes files."""
    # Create 7 reports (exceeds max_count=5)
    for i in range(7):
        report = reports_dir / f"pre-push-review-2024010{i}.md"
        report.write_text(f"report {i}")
        time.sleep(0.01)

    result = service.clean_reports("pre-push-review", dry_run=False)

    # Should actually delete
    assert result["kept"] == 5
    assert result["deleted"] == 2
    assert result["freed_bytes"] > 0
    # Files should be deleted
    assert len(list(reports_dir.glob("pre-push-review-*.md"))) == 5


def test_clean_reports_age_based(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """clean_reports deletes reports older than max_age_days."""
    # Create old report
    old_report = reports_dir / "pre-push-review-old.md"
    old_report.write_text("old report")
    # Set mtime to 60 days ago
    old_time = time.time() - (60 * 24 * 3600)
    import os

    os.utime(old_report, (old_time, old_time))

    # Create new report
    new_report = reports_dir / "pre-push-review-new.md"
    new_report.write_text("new report")

    result = service.clean_reports("pre-push-review", dry_run=False)

    # Old report should be deleted (exceeds max_age_days=30)
    assert not old_report.exists()
    # New report should be kept
    assert new_report.exists()
    assert result["deleted"] >= 1


def test_clean_reports_override_max_count(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """clean_reports respects override max_count."""
    # Create 5 reports
    for i in range(5):
        report = reports_dir / f"pre-push-review-2024010{i}.md"
        report.write_text(f"report {i}")
        time.sleep(0.01)

    # Override max_count to 2
    result = service.clean_reports("pre-push-review", dry_run=False, max_count=2)

    assert result["kept"] == 2
    assert result["deleted"] == 3


def test_clean_all(service: ReportCleanupService, reports_dir: Path) -> None:
    """clean_all cleans all report types."""
    # Create reports of different types
    pre_push = reports_dir / "pre-push-review-20240101.md"
    pre_push.write_text("pre-push review")

    skills_state = reports_dir / "skills-state-run1.json"
    skills_state.write_text('{"state": "running"}')

    audit = reports_dir / "audit-result.md"
    audit.write_text("audit result")

    results = service.clean_all(dry_run=False)

    # Should return results for each type
    assert isinstance(results, dict)
    assert "pre-push-review" in results
    assert "skills-state" in results
    assert "audit-result" in results


def test_get_disk_usage_empty(service: ReportCleanupService) -> None:
    """get_disk_usage returns zeros for empty directory."""
    usage = service.get_disk_usage()
    assert usage["total_bytes"] == 0
    assert usage["total_files"] == 0
    assert usage["total_dirs"] == 0


def test_get_disk_usage_with_files(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """get_disk_usage counts files and directories correctly."""
    # Create some files
    report1 = reports_dir / "pre-push-review-20240101.md"
    report1.write_text("x" * 1000)

    flow_dir = reports_dir / "task-issue-123"
    flow_dir.mkdir()
    coverage = flow_dir / "coverage.json"
    coverage.write_text('{"coverage": 80}')

    usage = service.get_disk_usage()
    assert usage["total_bytes"] > 0
    assert usage["total_files"] == 2
    assert (
        usage["total_dirs"] >= 1
    )  # flow_dir (reports_dir is counted separately by rglob)


def test_retention_policy_type_specific(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """Type-specific retention policy overrides defaults."""
    # Create 7 pre-push-review reports (max_count=5 for this type)
    for i in range(7):
        report = reports_dir / f"pre-push-review-2024010{i}.md"
        report.write_text(f"report {i}")
        time.sleep(0.01)

    result = service.clean_reports("pre-push-review", dry_run=False)

    # Should keep only 5 (type-specific override)
    assert result["kept"] == 5
    assert result["deleted"] == 2


def test_report_info_properties() -> None:
    """ReportInfo properties compute correct values."""
    info = ReportInfo(
        path=Path("/tmp/test.md"),
        size_bytes=2048,
        mtime=time.time(),
        age_days=0.5,
    )

    assert info.size_kb == 2.0
    assert info.age_display == "12.0h"


def test_list_reports_handles_missing_directory(
    config: VibeConfig,
) -> None:
    """list_reports returns empty list when directory doesn't exist."""
    service = ReportCleanupService(config=config)
    service.reports_dir = Path("/nonexistent")

    reports = service.list_reports("pre-push-review")
    assert reports == []


def test_clean_reports_handles_error(
    service: ReportCleanupService, reports_dir: Path
) -> None:
    """clean_reports handles file deletion errors gracefully."""
    # Create a report
    report = reports_dir / "pre-push-review-20240101.md"
    report.write_text("test")

    # Mock unlink to raise exception
    with patch.object(Path, "unlink", side_effect=PermissionError("No access")):
        result = service.clean_reports("pre-push-review", dry_run=False)

    # Should not crash, but deletion should fail
    assert result["deleted"] == 0
