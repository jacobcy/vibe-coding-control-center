"""Snapshot baseline operations - Save and load branch baselines."""

import json
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.models import StructureSnapshot


def save_branch_baseline(
    branch: str,
    force: bool = False,
    snapshot: StructureSnapshot | None = None,
    build_snapshot_func: Callable[[], StructureSnapshot] | None = None,
    _ensure_baseline_dir_func: Callable[[], None] | None = None,
    _get_baseline_dir_func: Callable[[], Path] | None = None,
    repo_path: Path | None = None,
) -> Path | None:
    """Build current snapshot and save as baseline for the specified branch.

    This function is called when a flow completes (PR merge or auto-complete).
    It builds a fresh snapshot and saves it with baseline_for tag.

    Args:
        branch: Branch name to save baseline for
        force: Force overwrite existing baseline (default: False)
        snapshot: Pre-built snapshot (optional, if None will build fresh)
        build_snapshot_func: Function to build snapshot if needed (dependency injection)
        _ensure_baseline_dir_func: Function to ensure baseline dir exists
        _get_baseline_dir_func: Function to get baseline dir path
        repo_path: Repository path for worktree-aware operations. When set,
            build_snapshot is called with repo_path argument.

    Returns:
        Path to saved baseline, or None if build failed
    """
    # Import snapshot_service helpers for default implementations
    # Local import to avoid circular dependency

    # When repo_path is provided, construct a lambda that passes it
    # to build_snapshot. This takes precedence over the default but
    # allows explicit build_snapshot_func override.
    if repo_path is not None and build_snapshot_func is None:
        from vibe3.analysis.snapshot_service import (
            build_snapshot as default_build_snapshot,
        )

        def _build_with_repo_path() -> StructureSnapshot:
            return default_build_snapshot(repo_path=repo_path)

        build_snapshot_func = _build_with_repo_path

    if build_snapshot_func is None:
        from vibe3.analysis.snapshot_service import (
            build_snapshot as default_build_snapshot,
        )

        build_snapshot_func = default_build_snapshot
    if _ensure_baseline_dir_func is None:
        from vibe3.analysis.snapshot_service import (
            _ensure_baseline_dir as default_ensure_baseline_dir,
        )

        _ensure_baseline_dir_func = default_ensure_baseline_dir
    if _get_baseline_dir_func is None:
        from vibe3.analysis.snapshot_service import (
            _get_baseline_dir as default_get_baseline_dir,
        )

        _get_baseline_dir_func = default_get_baseline_dir

    log = logger.bind(domain="snapshot", action="save_baseline", branch=branch)
    log.info("Saving branch baseline")

    try:
        # Use provided snapshot or build fresh
        if snapshot is None:
            snapshot = build_snapshot_func()
        snapshot.baseline_for = branch

        _ensure_baseline_dir_func()
        baseline_dir = _get_baseline_dir_func()

        # Sanitize branch name for filename safety
        safe_branch = branch.replace("/", "-")
        filename = f"baseline_{safe_branch}.json"
        filepath = baseline_dir / filename

        if filepath.exists() and not force:
            log.info("Baseline already exists, skipping (idempotent)")
            return filepath

        filepath.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")

        # Register in snapshot_registry for DB-backed lookup
        try:
            client = SQLiteClient()
            client.upsert_snapshot_registry(
                snapshot_id=snapshot.snapshot_id,
                branch=snapshot.branch,
                commit_short=snapshot.commit_short,
                commit_hash=snapshot.commit,
                created_at=snapshot.created_at,
                file_path=str(filepath),
                baseline_for=branch,
            )
        except Exception as e:
            logger.warning(
                f"Failed to register baseline in DB (non-fatal): "
                f"{type(e).__name__}: {e}"
            )

        log.bind(path=str(filepath)).success("Branch baseline saved")
        return filepath

    except Exception as e:
        logger.warning(f"Failed to save branch baseline: {e}")
        return None


def load_branch_baseline(
    branch: str,
    _get_baseline_dir_func: Callable[[], Path] | None = None,
) -> StructureSnapshot | None:
    """Load the most recent baseline snapshot for a branch.

    Args:
        branch: Branch name to load baseline for
        _get_baseline_dir_func: Function to get baseline dir path (dependency injection)

    Returns:
        StructureSnapshot for the branch baseline, or None if not found
    """
    # Import snapshot_service helper for default implementation
    if _get_baseline_dir_func is None:
        from vibe3.analysis.snapshot_service import (
            _get_baseline_dir as default_get_baseline_dir,
        )

        _get_baseline_dir_func = default_get_baseline_dir

    log = logger.bind(domain="snapshot", action="load_baseline", branch=branch)
    log.info("Loading branch baseline")

    try:
        baseline_dir = _get_baseline_dir_func()
        if not baseline_dir.exists():
            return None

        # Sanitize branch name for filename safety
        safe_branch = branch.replace("/", "-")
        filename = f"baseline_{safe_branch}.json"
        filepath = baseline_dir / filename

        if not filepath.exists():
            return None

        data = json.loads(filepath.read_text(encoding="utf-8"))
        snapshot = StructureSnapshot.model_validate(data)

        log.success("Branch baseline loaded")
        return snapshot

    except Exception as e:
        logger.warning(f"Failed to load branch baseline: {e}")
        return None


def backfill_baseline_registry(
    _get_baseline_dir_func: Callable[[], Path] | None = None,
) -> dict[str, int]:
    """Backfill snapshot_registry with baseline records from filesystem.

    This is a one-time repair function to recover orphaned baseline records
    that exist on disk but are missing from the database.

    Args:
        _get_baseline_dir_func: Function to get baseline dir path (dependency injection)

    Returns:
        Dict with counts: {"registered": int, "skipped": int, "failed": int}
    """
    # Import snapshot_service helper for default implementation
    if _get_baseline_dir_func is None:
        from vibe3.analysis.snapshot_service import (
            _get_baseline_dir as default_get_baseline_dir,
        )

        _get_baseline_dir_func = default_get_baseline_dir

    log = logger.bind(domain="snapshot", action="backfill_baselines")
    log.info("Backfilling baseline registry from filesystem")

    counts = {"registered": 0, "skipped": 0, "failed": 0}

    try:
        baseline_dir = _get_baseline_dir_func()
        if not baseline_dir.exists():
            log.info("No baseline directory found, nothing to backfill")
            return counts

        json_files = list(baseline_dir.glob("*.json"))
        log.info(f"Found {len(json_files)} baseline files to process")

        for filepath in json_files:
            try:
                # Read and parse the snapshot
                data = json.loads(filepath.read_text(encoding="utf-8"))
                snapshot = StructureSnapshot.model_validate(data)

                # Only process files with baseline_for field
                if not snapshot.baseline_for:
                    counts["skipped"] += 1
                    continue

                # Register in database
                client = SQLiteClient()
                client.upsert_snapshot_registry(
                    snapshot_id=snapshot.snapshot_id,
                    branch=snapshot.branch,
                    commit_short=snapshot.commit_short,
                    commit_hash=snapshot.commit,
                    created_at=snapshot.created_at,
                    file_path=str(filepath),
                    baseline_for=snapshot.baseline_for,
                )
                counts["registered"] += 1
                log.debug(f"Registered baseline: {filepath.name}")

            except Exception as e:
                counts["failed"] += 1
                logger.warning(
                    f"Failed to backfill baseline {filepath.name}: "
                    f"{type(e).__name__}: {e}"
                )

        log.info(
            f"Backfill complete: registered={counts['registered']}, "
            f"skipped={counts['skipped']}, failed={counts['failed']}"
        )

    except Exception as e:
        logger.error(f"Failed to backfill baseline registry: {e}")

    return counts
