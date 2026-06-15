"""Facade for snapshot diff with automatic fallback chain."""

from loguru import logger

from vibe3.analysis.snapshot_service import (
    build_snapshot,
    load_branch_baseline,
)
from vibe3.clients import GitClient
from vibe3.models import BranchSource, DiffSummary


def get_diff_summary(branch: str, base_branch: str = "main") -> DiffSummary:
    """Return a DiffSummary with fallback chain.

    1. Snapshot diff: if baseline exists → full structural comparison
    2. Git numstat: no baseline → per-file LOC + file counts
    3. Empty summary: extreme fallback → file count only
    """
    baseline = load_branch_baseline(branch)
    if baseline is not None:
        current = build_snapshot()
        from vibe3.analysis.snapshot_diff import compute_diff

        structure_diff = compute_diff(baseline, current)
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
    """Build DiffSummary from git numstat (fallback when no baseline).

    Uses GitClient.get_numstat() which resolves merge-base internally.
    File counts come from numstat line count (all counted as "modified"
    since A/M/D classification requires a separate --name-status call
    that GitClient has no public API for).
    """
    source = BranchSource(branch=branch, base=base_branch)
    loc_delta = 0
    file_count = 0

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
                file_count += 1
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

    return DiffSummary(
        files_modified=file_count,
        total_loc_delta=loc_delta,
    )
