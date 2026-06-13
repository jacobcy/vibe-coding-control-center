"""Service-layer helpers for review pipeline dependencies."""

from loguru import logger

from vibe3.analysis import (
    SnapshotError,
    build_change_analysis,
    build_snapshot,
    compute_diff,
    find_snapshot_by_branch,
)
from vibe3.exceptions import SystemError
from vibe3.models import StructureDiff

_SUBCOMMAND_TO_SOURCE_TYPE: dict[str, str] = {
    "pr": "pr",
    "base": "branch",
}


def run_inspect_json(args: list[str]) -> dict[str, object]:
    """Call inspect subcommand and return parsed JSON result."""
    if not args:
        raise SystemError("Missing inspect subcommand")

    subcommand = args[0]
    if subcommand not in _SUBCOMMAND_TO_SOURCE_TYPE:
        raise SystemError(f"Unknown inspect subcommand: {subcommand}")

    if len(args) < 2:
        raise SystemError(f"Missing identifier for inspect {subcommand}")

    identifier = args[1]

    source_type = _SUBCOMMAND_TO_SOURCE_TYPE[subcommand]
    return build_change_analysis(source_type, identifier)


def build_snapshot_diff(
    base_branch: str = "main", current_branch: str | None = None
) -> StructureDiff | None:
    """Build snapshot diff for review context."""
    log = logger.bind(domain="review", action="build_snapshot_diff")
    structure_diff: StructureDiff | None = None

    try:
        log.info(f"Loading baseline snapshot for branch: {base_branch}")
        baseline = find_snapshot_by_branch(base_branch, current_branch)

        if baseline is None:
            log.warning(f"No baseline snapshot found for branch: {base_branch}")
            return None

        log.info("Building current snapshot")
        current = build_snapshot()

        log.info("Computing structure diff")
        structure_diff = compute_diff(baseline, current)
        log.bind(
            files_changed=structure_diff.summary.files_added
            + structure_diff.summary.files_removed
            + structure_diff.summary.files_modified
        ).info("Structure diff computed")

    except SnapshotError as error:
        log.bind(error=str(error)).warning("Snapshot operation failed")
    except Exception as error:  # pragma: no cover - defensive
        log.bind(error=str(error)).error("Unexpected error building snapshot diff")

    return structure_diff
