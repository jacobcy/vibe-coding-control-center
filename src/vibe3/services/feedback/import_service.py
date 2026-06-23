"""Feedback import service: batch import from directory."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from vibe3.clients.feedback_store import FeedbackStore
from vibe3.services.feedback.write_service import FeedbackWriteService


class FeedbackImportService:
    """Service for batch importing observations from files."""

    def __init__(self, store: FeedbackStore | None = None) -> None:
        """Initialize with optional store dependency.

        Args:
            store: FeedbackStore instance. If None, creates a new one.
        """
        self.store = store or FeedbackStore()
        self.write_service = FeedbackWriteService(store=self.store)

    def import_from_directory(self, dir_path: Path) -> tuple[int, int]:
        """Import all YAML files from directory.

        Scans for .yaml and .yml files, parses each, and inserts into DB.
        Handles errors gracefully: skips files with errors, reports counts.

        Args:
            dir_path: Directory containing YAML files

        Returns:
            Tuple of (imported_count, skipped_count)

        Raises:
            FileNotFoundError: If directory doesn't exist
            NotADirectoryError: If path is not a directory
        """
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        imported = 0
        skipped = 0

        # Find all YAML files
        yaml_files = list(dir_path.glob("*.yaml")) + list(dir_path.glob("*.yml"))

        for yaml_file in yaml_files:
            try:
                self.write_service.write_from_file(yaml_file)
                imported += 1
                logger.bind(
                    external="feedback",
                    operation="import",
                ).debug(f"Imported {yaml_file.name}")
            except Exception as e:
                skipped += 1
                logger.bind(
                    external="feedback",
                    operation="import",
                ).warning(f"Skipped {yaml_file.name}: {e}")

        logger.bind(
            external="feedback",
            operation="import",
        ).info(f"Import complete: {imported} imported, {skipped} skipped")

        return (imported, skipped)
