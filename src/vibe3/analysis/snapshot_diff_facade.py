"""Facade for snapshot diff with automatic fallback chain."""

from loguru import logger

from vibe3.analysis.snapshot_service import (
    build_snapshot,
    load_branch_baseline,
)
from vibe3.clients import GitClient
from vibe3.models import BranchSource, ChangeSource, DiffSummary, UncommittedSource
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

    Collects both committed (branch vs base) and uncommitted (working tree vs HEAD)
    changes, matching inspect base behavior.
    """

    committed_source = BranchSource(branch=branch, base=base_branch)
    uncommitted_source = UncommittedSource()

    loc_delta = 0
    file_statuses: dict[str, str] = {}  # filepath -> status string
    committed_numstat = ""
    uncommitted_numstat = ""

    # Collect numstat from both sources (LOC delta is additive across
    # committed + uncommitted layers).
    sources: list[tuple[ChangeSource, str]] = [
        (committed_source, "committed"),
        (uncommitted_source, "uncommitted"),
    ]
    for source, tracker in sources:
        try:
            output = git.get_numstat(source)
            if tracker == "committed":
                committed_numstat = output
            else:
                uncommitted_numstat = output
            if output:
                for line in output.splitlines():
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
            ).warning(f"Failed to get git numstat for {source.type}: {e}")

    # Collect name-status from both sources. Process committed first, then
    # uncommitted — so uncommitted status overwrites committed for files
    # that appear in both (working-tree state is more current).
    name_status_sources: list[ChangeSource] = [
        committed_source,
        uncommitted_source,
    ]
    for source in name_status_sources:
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
                    filepath = parts[1]
                    file_statuses[filepath] = status
        except Exception as e:
            logger.bind(
                domain="snapshot",
                action="git_name_status",
                branch=branch,
            ).warning(f"Failed to get git name-status for {source.type}: {e}")

    # Count files by status
    files_added = 0
    files_removed = 0
    files_modified = 0
    for status in file_statuses.values():
        status_char = status[0]
        if status_char == "A":
            files_added += 1
        elif status_char == "D":
            files_removed += 1
        elif status_char == "M":
            files_modified += 1
        elif status_char == "R":
            files_added += 1
            files_removed += 1
        elif status_char == "C":
            files_added += 1

    # Fallback: if name-status failed for all sources, count distinct files
    # from numstat output.
    if not file_statuses:
        distinct_files: set[str] = set()
        for output in [committed_numstat, uncommitted_numstat]:
            if output:
                for line in output.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        distinct_files.add(parts[2])
        files_modified = len(distinct_files)
        files_added = 0
        files_removed = 0

    return DiffSummary(
        files_added=files_added,
        files_removed=files_removed,
        files_modified=files_modified,
        total_loc_delta=loc_delta,
    )
