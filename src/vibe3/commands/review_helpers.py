"""Review command helper functions."""

import json
import subprocess

import typer
from loguru import logger

from vibe3.models.snapshot import StructureDiff
from vibe3.services.snapshot_diff import compute_diff
from vibe3.services.snapshot_service import (
    SnapshotError,
    SnapshotNotFoundError,
    build_snapshot,
    load_snapshot,
)


def run_inspect_json(args: list[str]) -> dict[str, object]:
    """Call vibe inspect subcommand and return JSON result.

    Args:
        args: inspect subcommand argument list

    Returns:
        Parsed JSON dict

    Raises:
        typer.Exit: if inspect call fails
    """
    result = subprocess.run(
        ["uv", "run", "python", "-m", "vibe3", "inspect", *args, "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"inspect failed: {result.stderr}")
        raise typer.Exit(1)
    return json.loads(result.stdout)  # type: ignore


def build_snapshot_diff() -> StructureDiff | None:
    """Build snapshot diff for review context.

    Returns:
        StructureDiff if successful, None if failed or no baseline snapshot
    """
    log = logger.bind(domain="review", action="build_snapshot_diff")
    structure_diff: StructureDiff | None = None

    try:
        log.info("Building current snapshot")
        current = build_snapshot()

        log.info("Loading baseline snapshot")
        try:
            baseline = load_snapshot()
        except SnapshotNotFoundError:
            log.warning("No baseline snapshot found")
            return None

        log.info("Computing structure diff")
        structure_diff = compute_diff(baseline, current)
        log.bind(
            files_changed=structure_diff.summary.files_added
            + structure_diff.summary.files_removed
            + structure_diff.summary.files_modified
        ).info("Structure diff computed")

    except SnapshotError as e:
        log.bind(error=str(e)).warning("Snapshot operation failed")
    except Exception as e:
        log.bind(error=str(e)).error("Unexpected error building snapshot diff")

    return structure_diff
