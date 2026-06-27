"""DiffSummary model for change summaries."""

from __future__ import annotations

from pydantic import BaseModel


class DiffSummary(BaseModel):
    """Summary of structure changes."""

    files_added: int = 0
    files_removed: int = 0
    files_modified: int = 0
    modules_added: int = 0
    modules_removed: int = 0
    modules_modified: int = 0
    dependencies_added: int = 0
    dependencies_removed: int = 0
    total_loc_delta: int = 0
    total_functions_delta: int = 0

    def __add__(self, other: DiffSummary) -> DiffSummary:
        return DiffSummary(
            files_added=self.files_added + other.files_added,
            files_removed=self.files_removed + other.files_removed,
            files_modified=self.files_modified + other.files_modified,
            modules_added=self.modules_added + other.modules_added,
            modules_removed=self.modules_removed + other.modules_removed,
            modules_modified=self.modules_modified + other.modules_modified,
            dependencies_added=self.dependencies_added + other.dependencies_added,
            dependencies_removed=self.dependencies_removed + other.dependencies_removed,
            total_loc_delta=self.total_loc_delta + other.total_loc_delta,
            total_functions_delta=self.total_functions_delta
            + other.total_functions_delta,
        )
