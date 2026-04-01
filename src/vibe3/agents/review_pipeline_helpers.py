"""Service-layer helpers for review pipeline dependencies."""

import json
import subprocess
from typing import Any

import typer
from loguru import logger

from vibe3.analysis.snapshot_diff import compute_diff
from vibe3.analysis.snapshot_service import (
    SnapshotError,
    build_snapshot,
    find_snapshot_by_branch,
)
from vibe3.models.snapshot import StructureDiff


def run_inspect_json(args: list[str]) -> dict[str, object]:
    """Call inspect subcommand and return parsed JSON result."""
    result = subprocess.run(
        ["uv", "run", "python", "-m", "vibe3", "inspect", *args, "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"inspect failed: {result.stderr}")
        raise typer.Exit(1)
    payload: Any = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise typer.Exit(1)
    return {str(key): value for key, value in payload.items()}


def build_snapshot_diff(
    base_branch: str = "main", current_branch: str | None = None
) -> StructureDiff | None:
    """Build snapshot diff for review context."""
    log = logger.bind(domain="review", action="build_snapshot_diff")
    structure_diff: StructureDiff | None = None

    try:
        log.info("Building current snapshot")
        current = build_snapshot()

        log.info(f"Loading baseline snapshot for branch: {base_branch}")
        baseline = find_snapshot_by_branch(base_branch, current_branch)

        if baseline is None:
            log.warning(f"No baseline snapshot found for branch: {base_branch}")
            return None

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
