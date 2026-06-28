"""DiffSummary model for change summaries (git-only, no snapshot dependency)."""

from __future__ import annotations

from pydantic import BaseModel


class DiffSummary(BaseModel):
    """Summary of file-level changes from git diff.

    Fields retained from the retired snapshot subsystem (#3215):
    - files_added/removed/modified: file counts from git name-status
    - total_loc_delta: net LOC change from git numstat
    """

    files_added: int = 0
    files_removed: int = 0
    files_modified: int = 0
    total_loc_delta: int = 0

    def __add__(self, other: DiffSummary) -> DiffSummary:
        return DiffSummary(
            files_added=self.files_added + other.files_added,
            files_removed=self.files_removed + other.files_removed,
            files_modified=self.files_modified + other.files_modified,
            total_loc_delta=self.total_loc_delta + other.total_loc_delta,
        )
