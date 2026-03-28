"""Snapshot models for structure analysis."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FunctionSnapshot(BaseModel):
    """Function information in a snapshot."""

    name: str
    line: int
    loc: int


class FileSnapshot(BaseModel):
    """File information in a snapshot."""

    path: str
    language: str
    total_loc: int
    functions: list[FunctionSnapshot] = Field(default_factory=list)
    function_count: int = 0
    imports: list[str] = Field(default_factory=list)


class ModuleSnapshot(BaseModel):
    """Module (directory) information in a snapshot."""

    module: str  # e.g., "vibe3.services"
    file_count: int = 0
    total_loc: int = 0
    total_functions: int = 0
    files: list[str] = Field(default_factory=list)  # Relative paths


class DependencyEdge(BaseModel):
    """Dependency edge between modules."""

    from_module: str
    to_module: str


class StructureMetrics(BaseModel):
    """Aggregate metrics for a snapshot."""

    total_files: int = 0
    total_loc: int = 0
    total_functions: int = 0
    python_files: int = 0
    shell_files: int = 0
    avg_file_loc: float = 0.0
    avg_functions_per_file: float = 0.0


class StructureSnapshot(BaseModel):
    """Complete structure snapshot."""

    snapshot_id: str  # Format: "{timestamp}_{branch}_{commit_short}"
    branch: str
    commit: str  # Full commit SHA
    commit_short: str  # Short commit SHA (7 chars)
    created_at: str  # ISO 8601 timestamp
    root: str  # Analysis root (e.g., "src/vibe3")
    files: list[FileSnapshot] = Field(default_factory=list)
    modules: list[ModuleSnapshot] = Field(default_factory=list)
    dependencies: list[DependencyEdge] = Field(default_factory=list)
    metrics: StructureMetrics = Field(default_factory=StructureMetrics)

    @classmethod
    def generate_id(
        cls, branch: str, commit_short: str, timestamp: str | None = None
    ) -> str:
        """Generate a snapshot ID.

        Args:
            branch: Git branch name
            commit_short: Short commit SHA (7 chars)
            timestamp: ISO 8601 timestamp (defaults to now)

        Returns:
            Snapshot ID in format: "{timestamp}_{branch}_{commit_short}"
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat(timespec="seconds")
        # Replace colons with hyphens for filename safety
        safe_timestamp = timestamp.replace(":", "-")
        # Sanitize branch name for filename safety
        safe_branch = branch.replace("/", "-")
        return f"{safe_timestamp}_{safe_branch}_{commit_short}"


class FileChange(BaseModel):
    """Change in a single file."""

    path: str
    change_type: Literal["added", "removed", "modified"]
    old_loc: int | None = None  # None for added files
    new_loc: int | None = None  # None for removed files
    old_function_count: int | None = None
    new_function_count: int | None = None


class ModuleChange(BaseModel):
    """Change in a module."""

    module: str
    change_type: Literal["added", "removed", "modified"]
    old_file_count: int | None = None
    new_file_count: int | None = None
    old_loc: int | None = None
    new_loc: int | None = None


class DependencyChange(BaseModel):
    """Change in dependencies."""

    change_type: Literal["added", "removed"]
    from_module: str
    to_module: str


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


class DiffWarning(BaseModel):
    """Warning in structure diff."""

    type: Literal[
        "file_too_large",
        "module_growth",
        "dependency_cycle",
        "missing_imports",
        "unusual_pattern",
    ]
    severity: Literal["info", "warning", "error"]
    message: str
    file: str | None = None
    module: str | None = None
    details: dict = Field(default_factory=dict)


class StructureDiff(BaseModel):
    """Difference between two snapshots."""

    baseline_id: str
    baseline_branch: str
    baseline_commit: str
    current_id: str
    current_branch: str
    current_commit: str
    created_at: str  # ISO 8601 timestamp
    summary: DiffSummary = Field(default_factory=DiffSummary)
    file_changes: list[FileChange] = Field(default_factory=list)
    module_changes: list[ModuleChange] = Field(default_factory=list)
    dependency_changes: list[DependencyChange] = Field(default_factory=list)
    warnings: list[DiffWarning] = Field(default_factory=list)
