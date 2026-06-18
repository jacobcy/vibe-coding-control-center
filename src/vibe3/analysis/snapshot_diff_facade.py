"""Facade for snapshot diff with automatic fallback chain."""

from loguru import logger

from vibe3.analysis.snapshot_service import (
    build_snapshot,
    load_branch_baseline,
)
from vibe3.clients import GitClient
from vibe3.models import BranchSource, DiffSummary
from vibe3.utils import DEFAULT_MODULE_GROWTH_THRESHOLD


def get_diff_summary(
    branch: str,
    base_branch: str = "main",
    module_growth_threshold: int | None = None,
) -> DiffSummary:
    """Return a DiffSummary with fallback chain.

    1. Snapshot diff: if baseline exists → full structural comparison
    2. Git numstat: no baseline → per-file LOC + file counts
    3. Empty summary: extreme fallback → file count only
    """
    baseline = load_branch_baseline(branch)
    if baseline is not None:
        current = build_snapshot()
        from vibe3.analysis.snapshot_diff import compute_diff

        threshold = (
            module_growth_threshold
            if module_growth_threshold is not None
            else DEFAULT_MODULE_GROWTH_THRESHOLD
        )
        structure_diff = compute_diff(baseline, current, threshold)
        return structure_diff.summary

    try:
        git = GitClient()
        return _diff_via_git(git, branch, base_branch)
    except Exception as e:
        logger.bind(
            domain="snapshot",
            action="diff_fallback",
            branch=branch,
        ).warning(f"Git diff fallback failed: {e}")

    return DiffSummary()


def _diff_via_git(git: GitClient, branch: str, base_branch: str) -> DiffSummary:
    """Build DiffSummary from git numstat + name-status (fallback when no baseline).

    Uses GitClient.get_numstat() for LOC delta and get_name_status() for
    A/M/D file classification. Falls back to all-modified on name-status failure.
    """
    source = BranchSource(branch=branch, base=base_branch)
    loc_delta = 0
    files_added = 0
    files_removed = 0
    files_modified = 0

    # Get LOC delta from numstat
    try:
        numstat_output = git.get_numstat(source)
        if numstat_output:
            for line in numstat_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                try:
                    a = int(parts[0]) if parts[0] != "-" else 0
                    r = int(parts[1]) if parts[1] != "-" else 0
                    loc_delta += a - r
                except ValueError:
                    pass
    except Exception as e:
        logger.bind(
            domain="snapshot",
            action="git_numstat",
            branch=branch,
        ).warning(f"Failed to get git numstat: {e}")

    # Get A/M/D classification from name-status
    try:
        name_status_output = git.get_name_status(source)
        if name_status_output:
            for line in name_status_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                status = parts[0]
                # Status format: first char is the type, may have score (e.g., R100)
                status_char = status[0]
                if status_char == "A":
                    files_added += 1
                elif status_char == "D":
                    files_removed += 1
                elif status_char == "M":
                    files_modified += 1
                elif status_char == "R":
                    # Rename counts as add + remove
                    files_added += 1
                    files_removed += 1
                elif status_char == "C":
                    # Copy counts as add
                    files_added += 1
    except Exception as e:
        logger.bind(
            domain="snapshot",
            action="git_name_status",
            branch=branch,
        ).warning(f"Failed to get git name-status, falling back to all-modified: {e}")
        # Fallback: count all files as modified based on numstat line count
        file_count = 0
        if numstat_output:
            for line in numstat_output.splitlines():
                if line.strip():
                    file_count += 1
        files_modified = file_count
        files_added = 0
        files_removed = 0

    return DiffSummary(
        files_added=files_added,
        files_removed=files_removed,
        files_modified=files_modified,
        total_loc_delta=loc_delta,
    )
