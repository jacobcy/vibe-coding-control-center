"""Type definitions for report cleanup service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class CleanupResult(TypedDict):
    """Result of cleanup operation."""

    kept: int
    deleted: int
    freed_bytes: int
    files_deleted: list[str]


@dataclass
class ReportInfo:
    """Information about a report file."""

    path: Path
    size_bytes: int
    mtime: float  # Unix timestamp
    age_days: float

    @property
    def size_kb(self) -> float:
        """Size in kilobytes."""
        return self.size_bytes / 1024

    @property
    def age_display(self) -> str:
        """Human-readable age."""
        if self.age_days < 1:
            hours = self.age_days * 24
            return f"{hours:.1f}h"
        return f"{self.age_days:.1f}d"


@dataclass
class ReportTypeDefinition:
    """Definition of a report type with its file pattern."""

    name: str
    pattern: str  # Glob pattern
    is_subdirectory: bool  # Whether reports are in subdirectories
