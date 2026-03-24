"""Snapshot lookup utilities for finding snapshots by branch or commit."""

import json

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.models.snapshot import StructureSnapshot
from vibe3.services.snapshot_service import _get_snapshot_dir, load_snapshot


def find_snapshot_by_branch(
    branch: str, current_branch: str | None = None
) -> StructureSnapshot | None:
    """Find the most appropriate snapshot for a specific branch.

    If current_branch is provided, finds the snapshot closest to the merge-base
    between branch and current_branch. Otherwise, returns the most recent snapshot.

    Args:
        branch: Branch name to search for (e.g., "main", "origin/main")
        current_branch: Current branch name (optional, for merge-base selection)

    Returns:
        Most appropriate StructureSnapshot for the branch, or None if not found
    """
    snapshot_dir = _get_snapshot_dir()
    if not snapshot_dir.exists():
        return None

    # Normalize branch name for comparison
    normalized_branch = branch.replace("origin/", "")

    snapshots = []
    for fp in snapshot_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            snapshot_branch = data.get("branch", "")
            if snapshot_branch == normalized_branch or snapshot_branch == branch:
                snapshots.append(
                    {
                        "id": data.get("snapshot_id", fp.stem),
                        "created_at": data.get("created_at", ""),
                        "branch": snapshot_branch,
                        "commit": data.get("commit", ""),
                    }
                )
        except (json.JSONDecodeError, KeyError):
            continue

    if not snapshots:
        return None

    # If current_branch is provided, find snapshot closest to merge-base
    if current_branch:
        try:
            git = GitClient()
            merge_base = git.get_merge_base(branch, current_branch)
            merge_base_short = merge_base[:7] if merge_base else None

            # Find snapshot with commit closest to merge-base
            for snap in snapshots:
                if snap["commit"][:7] == merge_base_short:
                    return load_snapshot(snap["id"])

            # If no exact match, fall back to most recent
            logger.warning(
                f"No snapshot for merge-base {merge_base_short}, using most recent"
            )
        except Exception as e:
            logger.warning(f"Failed to get merge-base: {e}, using most recent")

    # Sort by created_at descending and return the most recent
    snapshots.sort(key=lambda x: x["created_at"], reverse=True)
    return load_snapshot(snapshots[0]["id"])
