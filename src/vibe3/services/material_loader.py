"""Dispatch-time loader for governance material files (.md)."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from vibe3.prompts import MaterialEntry

logger = logging.getLogger(__name__)


class MaterialLoader:
    """Dispatch-time loader for governance material files (.md).

    Scans a directory for markdown files, reads their content,
    and computes stable content hashes. No process-level caching —
    each instantiation reads from disk (satisfying ADR-0003 dispatch-time boundary).
    """

    def __init__(self, base_dir: Path) -> None:
        """Initialize the loader with a base directory.

        Args:
            base_dir: Directory to scan for .md files.
        """
        self._base_dir = base_dir

    def load_all(self) -> tuple[MaterialEntry, ...]:
        """Load all .md files from the base directory.

        Returns empty tuple if directory doesn't exist or has no .md files.
        """
        if not self._base_dir.exists():
            logger.warning(f"Material directory does not exist: {self._base_dir}")
            return ()

        if not self._base_dir.is_dir():
            logger.warning(f"Material path is not a directory: {self._base_dir}")
            return ()

        entries: list[MaterialEntry] = []
        for md_file in sorted(self._base_dir.glob("*.md")):
            entry = self.load(md_file.name)
            if entry is not None:
                entries.append(entry)

        return tuple(entries)

    def load(self, name: str) -> MaterialEntry | None:
        """Load a single material by relative name.

        Args:
            name: Relative filename (e.g., "assignee-pool.md").

        Returns:
            MaterialEntry if file exists and is readable, None otherwise.
        """
        file_path = self._base_dir / name

        if not file_path.exists():
            return None

        if not file_path.is_file():
            logger.warning(f"Material path is not a file: {file_path}")
            return None

        try:
            content = file_path.read_text(encoding="utf-8")
            stat = file_path.stat()
            content_hash = self._compute_hash(content)

            return MaterialEntry(
                path=file_path.resolve(),
                name=name,
                content=content,
                content_hash=content_hash,
                mtime=stat.st_mtime,
            )
        except Exception as e:
            logger.warning(f"Failed to load material {file_path}: {e}")
            return None

    def _compute_hash(self, content: str) -> str:
        """SHA-256 hash of content, truncated to 16 hex chars."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
