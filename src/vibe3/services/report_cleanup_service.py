"""Report cleanup service - manages retention policy for .agent/reports/ directory.

This service provides cleanup of old reports based on configurable retention policy:
- Max count per report type
- Max age in days
- Type-specific retention overrides
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.services.report_cleanup_types import (
    CleanupResult,
    ReportInfo,
    ReportTypeDefinition,
)

if TYPE_CHECKING:
    from vibe3.config.settings import ReportsRetentionTypeConfig, VibeConfig


class ReportCleanupService:
    """Service for cleaning up old reports based on retention policy.

    The service manages cleanup of various report types in .agent/reports/:
    - pre-push-review-*.md
    - serena-impact.json
    - skills-state-*.json
    - skills-analysis-*.md
    - rules-report.md
    - coverage.json (in subdirectories)
    - audit-result.md

    Retention policy is configurable via config/settings.yaml:
    - max_count: Maximum reports to keep per type (default: 10)
    - max_age_days: Maximum age in days (default: 30)
    - types: Type-specific retention overrides
    """

    REPORTS_DIR = Path(".agent/reports")

    # Define report types with their patterns
    REPORT_TYPES: list[ReportTypeDefinition] = [
        ReportTypeDefinition(
            name="pre-push-review",
            pattern="pre-push-review-*.md",
            is_subdirectory=False,
        ),
        ReportTypeDefinition(
            name="serena-impact", pattern="serena-impact.json", is_subdirectory=False
        ),
        ReportTypeDefinition(
            name="skills-state", pattern="skills-state-*.json", is_subdirectory=False
        ),
        ReportTypeDefinition(
            name="skills-analysis",
            pattern="skills-analysis-*.md",
            is_subdirectory=False,
        ),
        ReportTypeDefinition(
            name="rules-report", pattern="rules-report.md", is_subdirectory=False
        ),
        ReportTypeDefinition(
            name="coverage", pattern="coverage.json", is_subdirectory=True
        ),
        ReportTypeDefinition(
            name="audit-result", pattern="audit-result.md", is_subdirectory=False
        ),
    ]

    def __init__(self, config: VibeConfig | None = None) -> None:
        """Initialize report cleanup service.

        Args:
            config: Optional VibeConfig instance. If None, loads via get_config().
        """
        if config is None:
            from vibe3.config.loader import get_config

            config = get_config()

        self.config = config
        self.reports_dir = self.REPORTS_DIR

    def get_report_types(self) -> list[ReportTypeDefinition]:
        """Return list of report type definitions.

        Returns:
            List of ReportTypeDefinition objects.
        """
        return self.REPORT_TYPES

    def list_reports(self, report_type: str) -> list[ReportInfo]:
        """List all reports of a given type with metadata.

        Args:
            report_type: Name of report type (e.g., "pre-push-review").

        Returns:
            List of ReportInfo objects for matching reports.
        """
        type_def = self._get_type_definition(report_type)
        if not type_def:
            logger.bind(
                domain="cleanup",
                action="list_reports",
                report_type=report_type,
            ).warning("Unknown report type")
            return []

        reports: list[ReportInfo] = []
        current_time = time.time()

        if not self.reports_dir.exists():
            logger.bind(
                domain="cleanup",
                action="list_reports",
                report_type=report_type,
            ).debug("Reports directory does not exist")
            return []

        if type_def.is_subdirectory:
            # For subdirectory reports, search in all subdirectories
            for subdir in self.reports_dir.iterdir():
                if subdir.is_dir():
                    for report_file in subdir.glob(type_def.pattern):
                        info = self._get_report_info(report_file, current_time)
                        if info:
                            reports.append(info)
        else:
            # For flat reports, search directly in reports directory
            if self.reports_dir.exists():
                for report_file in self.reports_dir.glob(type_def.pattern):
                    info = self._get_report_info(report_file, current_time)
                    if info:
                        reports.append(info)

        # Sort by mtime (newest first)
        reports.sort(key=lambda r: r.mtime, reverse=True)

        logger.bind(
            domain="cleanup",
            action="list_reports",
            report_type=report_type,
            count=len(reports),
        ).debug("Found reports")

        return reports

    def clean_reports(
        self,
        report_type: str,
        dry_run: bool = True,
        max_count: int | None = None,
        max_age_days: int | None = None,
    ) -> CleanupResult:
        """Clean old reports for a specific type.

        Args:
            report_type: Name of report type.
            dry_run: If True, only preview deletions without executing.
            max_count: Override config max_count for this type.
            max_age_days: Override config max_age_days for this type.

        Returns:
            Dict with:
                - kept: Number of reports kept
                - deleted: Number of reports deleted
                - freed_bytes: Total bytes freed
                - files_deleted: List of deleted file paths (for dry_run preview)
        """
        # Get retention policy (prefer args over config)
        retention = self._get_retention_policy(report_type)
        effective_max_count = (
            max_count if max_count is not None else retention.max_count or 10
        )
        effective_max_age = (
            max_age_days if max_age_days is not None else retention.max_age_days or 30
        )

        reports = self.list_reports(report_type)

        # Determine which reports to keep and delete
        to_keep: list[ReportInfo] = []
        to_delete: list[ReportInfo] = []

        for report in reports:
            # Keep if within max_count
            if len(to_keep) < effective_max_count:
                # Also check age
                if report.age_days <= effective_max_age:
                    to_keep.append(report)
                else:
                    to_delete.append(report)
            else:
                # Exceeds max_count, delete
                to_delete.append(report)

        # Delete reports (or preview)
        deleted_count = 0
        freed_bytes = 0
        files_deleted: list[str] = []

        for report in to_delete:
            if not dry_run:
                try:
                    report.path.unlink()
                    deleted_count += 1
                    freed_bytes += report.size_bytes
                    logger.bind(
                        domain="cleanup",
                        action="clean_reports",
                        report_type=report_type,
                        file=str(report.path),
                    ).debug("Deleted report")
                except Exception as exc:
                    logger.bind(
                        domain="cleanup",
                        action="clean_reports",
                        report_type=report_type,
                        file=str(report.path),
                    ).warning(f"Failed to delete: {exc}")
            else:
                files_deleted.append(str(report.path))

        if not dry_run:
            logger.bind(
                domain="cleanup",
                action="clean_reports",
                report_type=report_type,
                kept=len(to_keep),
                deleted=deleted_count,
                freed_bytes=freed_bytes,
            ).info("Cleaned reports")

        return {
            "kept": len(to_keep),
            "deleted": deleted_count if not dry_run else len(to_delete),
            "freed_bytes": (
                freed_bytes if not dry_run else sum(r.size_bytes for r in to_delete)
            ),
            "files_deleted": files_deleted,
        }

    def clean_all(self, dry_run: bool = True) -> dict[str, CleanupResult]:
        """Clean all report types.

        Args:
            dry_run: If True, only preview deletions without executing.

        Returns:
            Dict mapping report type to cleanup results.
        """
        results: dict[str, CleanupResult] = {}

        for type_def in self.REPORT_TYPES:
            results[type_def.name] = self.clean_reports(type_def.name, dry_run=dry_run)

        logger.bind(
            domain="cleanup",
            action="clean_all",
            dry_run=dry_run,
        ).info("Cleaned all report types")

        return results

    def get_disk_usage(self) -> dict[str, int]:
        """Get disk usage summary for reports directory.

        Returns:
            Dict with:
                - total_bytes: Total size in bytes
                - total_files: Total number of files
                - total_dirs: Total number of subdirectories
        """
        if not self.reports_dir.exists():
            return {"total_bytes": 0, "total_files": 0, "total_dirs": 0}

        total_bytes = 0
        total_files = 0
        total_dirs = 0

        for item in self.reports_dir.rglob("*"):
            if item.is_file():
                try:
                    total_bytes += item.stat().st_size
                    total_files += 1
                except Exception:
                    pass
            elif item.is_dir():
                total_dirs += 1

        return {
            "total_bytes": total_bytes,
            "total_files": total_files,
            "total_dirs": total_dirs,
        }

    def _get_type_definition(self, report_type: str) -> ReportTypeDefinition | None:
        """Get type definition by name.

        Args:
            report_type: Name of report type.

        Returns:
            ReportTypeDefinition or None if not found.
        """
        for type_def in self.REPORT_TYPES:
            if type_def.name == report_type:
                return type_def
        return None

    def _get_retention_policy(self, report_type: str) -> "ReportsRetentionTypeConfig":
        """Get effective retention policy for a report type.

        Args:
            report_type: Name of report type.

        Returns:
            ReportsRetentionTypeConfig with effective values.
        """
        from vibe3.config.settings import ReportsRetentionTypeConfig

        # Check for type-specific override
        if report_type in self.config.reports.retention.types:
            type_config = self.config.reports.retention.types[report_type]
            # Use type-specific values, fall back to defaults
            return ReportsRetentionTypeConfig(
                max_count=(
                    type_config.max_count or self.config.reports.retention.max_count
                ),
                max_age_days=(
                    type_config.max_age_days
                    or self.config.reports.retention.max_age_days
                ),
            )

        # Use default values
        return ReportsRetentionTypeConfig(
            max_count=self.config.reports.retention.max_count,
            max_age_days=self.config.reports.retention.max_age_days,
        )

    def _get_report_info(
        self, report_file: Path, current_time: float
    ) -> ReportInfo | None:
        """Get ReportInfo for a file.

        Args:
            report_file: Path to report file.
            current_time: Current Unix timestamp.

        Returns:
            ReportInfo or None if file cannot be accessed.
        """
        try:
            stat = report_file.stat()
            age_seconds = current_time - stat.st_mtime
            age_days = age_seconds / (24 * 3600)

            return ReportInfo(
                path=report_file,
                size_bytes=stat.st_size,
                mtime=stat.st_mtime,
                age_days=age_days,
            )
        except Exception as exc:
            logger.bind(
                domain="cleanup",
                action="get_report_info",
                file=str(report_file),
            ).warning(f"Failed to get file info: {exc}")
            return None
