"""Facade for snapshot diff with automatic fallback chain."""

from loguru import logger

from vibe3.analysis.snapshot_service import (
    build_snapshot,
    load_branch_baseline,
)
from vibe3.clients import GitClient
from vibe3.models import DiffSummary


def get_diff_summary(branch: str, base_branch: str = "main") -> DiffSummary:
    """Return a DiffSummary with fallback chain.

    1. Snapshot diff: if baseline exists → full structural comparison
    2. Git numstat: no baseline → per-file LOC + file counts
    3. Name-only: extreme fallback → file count only

    The caller determines how to render the result (Markdown table,
    CLI text, etc.). Fields unavailable in a fallback level are left
    at their default (0/NULL).
    """
    # Level 1: Full snapshot diff
    baseline = load_branch_baseline(branch)
    if baseline is not None:
        current = build_snapshot()
        from vibe3.analysis.snapshot_diff import compute_diff

        structure_diff = compute_diff(baseline, current)
        return structure_diff.summary

    # Level 2: Git diff --numstat + --name-status
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
    """Build DiffSummary from git diff output (fallback when no baseline)."""
    added = removed = modified = 0
    loc_delta = 0

    # Get file statuses via --name-status
    try:
        name_status_output = git._run(
            ["diff", "--name-status", f"{base_branch}...{branch}"]
        )
        if name_status_output:
            for line in name_status_output.splitlines():
                if line.startswith("A\t"):
                    added += 1
                elif line.startswith("D\t"):
                    removed += 1
                elif line.startswith("M\t"):
                    modified += 1
                elif len(line) > 0 and line[0] in "RC":
                    # Handle Rename (R) and Copy (C)
                    # Format: R100\told\tnew or C100\told\tnew
                    if line[0] == "R":
                        modified += 1
                    else:  # Copy
                        added += 1
    except Exception as e:
        logger.bind(
            domain="snapshot",
            action="git_name_status",
            branch=branch,
        ).warning(f"Failed to get git name-status: {e}")

    # Get Loc via --numstat
    try:
        numstat_output = git._run(["diff", "--numstat", f"{base_branch}...{branch}"])
        if numstat_output:
            for line in numstat_output.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
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
        files_added=added,
        files_removed=removed,
        files_modified=modified,
        total_loc_delta=loc_delta,
    )
