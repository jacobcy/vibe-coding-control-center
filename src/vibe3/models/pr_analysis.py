"""Type definitions for PR analysis."""

from dataclasses import dataclass
from typing import TypedDict


class CriticalFileInfo(TypedDict):
    """Information about a critical file."""

    path: str
    critical_path: bool
    public_api: bool


class CommitInfo(TypedDict):
    """Commit information for display."""

    sha: str
    message: str


@dataclass
class PRCriticalAnalysis:
    """PR critical analysis result.

    Attributes:
        pr_number: PR number
        total_commits: Total number of commits in PR
        total_files: Total number of changed files
        critical_files: List of critical files with their tags
        critical_symbols: Dict mapping files to their changed symbols
        impacted_modules: List of impacted modules from DAG analysis
        critical_file_dags: Dict mapping critical files to their DAG impact
        score: Risk score report
        recent_commits: List of recent commits (if verbose)
        skipped_files_count: Number of files skipped (no longer exist)
    """

    pr_number: int
    total_commits: int
    total_files: int
    critical_files: list[CriticalFileInfo]
    critical_symbols: dict[str, list[str]]
    impacted_modules: list[str]
    critical_file_dags: dict[str, list[str]]
    score: dict
    recent_commits: list[CommitInfo]
    skipped_files_count: int = 0
