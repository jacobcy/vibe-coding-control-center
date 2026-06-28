"""Git-only diff summary for PR change summaries."""

from loguru import logger

from vibe3.clients import GitClient
from vibe3.models import BranchSource, ChangeSource, DiffSummary, UncommittedSource


def get_git_diff_summary(
    branch: str,
    base_branch: str = "main",
) -> DiffSummary:
    """Build DiffSummary from git numstat + name-status.

    Collects both committed (branch vs base) and uncommitted (working tree vs HEAD)
    changes, matching inspect base behavior.

    The committed diff is computed from the merge-base of base_branch and HEAD,
    ensuring accurate comparison point for PR change summaries.
    """
    git = GitClient()

    # Resolve merge-base for accurate diff baseline
    merge_base = None
    try:
        merge_base = git.get_merge_base(base_branch, branch)
    except Exception as e:
        logger.bind(
            domain="git_diff",
            action="git_merge_base",
            branch=branch,
            base=base_branch,
        ).warning(f"Failed to resolve merge-base: {e}")

    # Use merge-base if available, otherwise fall back to base_branch
    effective_base = merge_base if merge_base else base_branch

    committed_source = BranchSource(branch=branch, base=effective_base)
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
                domain="git_diff",
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
                domain="git_diff",
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
