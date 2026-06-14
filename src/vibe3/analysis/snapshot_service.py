"""Snapshot service - Build, load, and manage structure snapshots."""

import glob as glob_mod
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from vibe3.analysis import dag_service, structure_service
from vibe3.clients import GitClient
from vibe3.exceptions import VibeError
from vibe3.models import (
    DependencyEdge,
    FileSnapshot,
    FunctionSnapshot,
    ModuleSnapshot,
    StructureDiff,
    StructureMetrics,
    StructureSnapshot,
)

_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        ".worktrees",
        ".codex",
        "temp",
        ".agent/plans",
    }
)

_LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".sh": "shell",
    ".zsh": "shell",
    ".bash": "shell",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".toml": "toml",
    ".json": "json",
    ".cfg": "config",
    ".ini": "config",
    ".txt": "text",
    ".csv": "csv",
    ".lock": "lock",
}


class SnapshotError(VibeError):
    """Snapshot operation failed."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Snapshot error: {details}", recoverable=False)


class SnapshotNotFoundError(SnapshotError):
    """Snapshot not found."""

    def __init__(self, snapshot_id: str) -> None:
        super().__init__(f"Snapshot not found: {snapshot_id}")


SNAPSHOT_DIR_NAME = "vibe3/structure/snapshots"
SNAPSHOT_TAG_DIR_NAME = "vibe3/structure/baselines"
LATEST_LINK_NAME = "vibe3/structure/latest.json"


def _get_snapshot_dir() -> Path:
    git = GitClient()
    return Path(git.get_git_common_dir()) / SNAPSHOT_DIR_NAME


def _get_latest_link_path() -> Path:
    git = GitClient()
    return Path(git.get_git_common_dir()) / LATEST_LINK_NAME


def _ensure_snapshot_dir() -> None:
    _get_snapshot_dir().mkdir(parents=True, exist_ok=True)


def _get_baseline_dir() -> Path:
    git = GitClient()
    return Path(git.get_git_common_dir()) / SNAPSHOT_TAG_DIR_NAME


def _ensure_baseline_dir() -> None:
    _get_baseline_dir().mkdir(parents=True, exist_ok=True)


def _get_module_from_path(file_path: str, root: str = "src/vibe3") -> str:
    p = Path(file_path)
    if root in str(p):
        parts = str(p).split(root + "/")
        if len(parts) > 1:
            module_parts = parts[1].split("/")
            if len(module_parts) > 1:
                return "vibe3." + ".".join(module_parts[:-1])
            return "vibe3"
    return "vibe3"


def _detect_language(file_path: str) -> str:
    """Detect file language from extension and path hints."""
    p = Path(file_path)
    ext = p.suffix.lower()
    lang = _LANG_BY_EXT.get(ext, "other")
    return lang


def _resolve_snapshot_repo_root(root: str) -> Path:
    """Infer the repository root that owns the provided source root."""
    root_path = Path(root).resolve()
    if root_path.name == "vibe3" and root_path.parent.name == "src":
        return root_path.parent.parent
    return root_path


def _collect_other_file_snapshots(
    tracked_dirs: list[str], repo_root: Path
) -> list[FileSnapshot]:
    """Collect basic snapshots for non-Python files in tracked directories."""
    files: list[FileSnapshot] = []
    seen: set[str] = set()
    cwd = Path.cwd().resolve()

    for top_dir in tracked_dirs:
        top = Path(top_dir) if repo_root == cwd else repo_root / top_dir
        if not top.exists() or not top.is_dir():
            continue
        for f in sorted(top.rglob("*")):
            if not f.is_file():
                continue
            rel = str(f)
            # Skip excluded dirs
            parts = rel.split("/")
            if any(part in _EXCLUDED_DIRS for part in parts):
                continue
            # Skip if already tracked by Python analysis
            if rel in seen:
                continue
            # Skip hidden files
            if any(p.startswith(".") for p in parts[:-1]):
                continue
            # Skip symlinks to files already tracked
            if f.is_symlink():
                continue
            # Count lines
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                loc = len(text.splitlines())
            except Exception:
                loc = 0
            lang = _detect_language(rel)
            if lang == "other":
                continue  # Skip unknown binary files

            seen.add(rel)
            files.append(FileSnapshot(path=rel, language=lang, total_loc=loc))
    return files


def build_snapshot(root: str | None = None) -> StructureSnapshot:
    """Build a structure snapshot from the current codebase.

    By default scans Python files in src/vibe3/ plus all non-Python files
    tracked by review_scope paths (skills/, supervisor/, config/, etc.).
    """
    if root is None:
        from vibe3.config import get_source_root

        root = get_source_root()
    log = logger.bind(domain="snapshot", action="build", root=root)
    log.info("Building structure snapshot")

    try:
        git = GitClient()
        branch = git.get_current_branch()
        commit = git.get_current_commit()
        commit_short = commit[:7] if commit else "unknown"
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        snapshot_id = StructureSnapshot.generate_id(branch, commit_short, timestamp)

        repo_root = _resolve_snapshot_repo_root(root)

        # Scan Python files (deep AST analysis)
        file_structures = structure_service.collect_python_file_structures(root)
        files: list[FileSnapshot] = []
        module_map: dict[str, ModuleSnapshot] = {}
        file_paths_seen: set[str] = set()

        for file_struct in file_structures:
            rel_path = file_struct.path
            file_paths_seen.add(rel_path)
            imports = dag_service._extract_imports(rel_path)

            file_snapshot = FileSnapshot(
                path=rel_path,
                language="python",
                total_loc=file_struct.total_loc,
                functions=[
                    FunctionSnapshot(name=f.name, line=f.line, loc=f.loc)
                    for f in file_struct.functions
                ],
                function_count=file_struct.function_count,
                imports=imports,
            )
            files.append(file_snapshot)

            module = _get_module_from_path(rel_path, root)
            if module not in module_map:
                module_map[module] = ModuleSnapshot(
                    module=module,
                    files=[],
                    file_count=0,
                    total_loc=0,
                    total_functions=0,
                )
            module_map[module].files.append(rel_path)
            module_map[module].file_count += 1
            module_map[module].total_loc += file_struct.total_loc
            module_map[module].total_functions += file_struct.function_count

        # Scan non-Python files from review_scope config paths directly
        from vibe3.config import get_config

        config = get_config()
        tracked_dirs: set[str] = set()
        for entry in (
            config.review_scope.critical_paths + config.review_scope.public_api_paths
        ):
            tracked_dirs.add(entry.split("/")[0])
        other_files = _collect_other_file_snapshots(sorted(tracked_dirs), repo_root)
        for f_snap in other_files:
            if f_snap.path not in file_paths_seen:
                files.append(f_snap)
                file_paths_seen.add(f_snap.path)
                # Create a basic module entry based on top-level dir
                top_dir = f_snap.path.split("/")[0]
                if top_dir not in module_map:
                    module_map[top_dir] = ModuleSnapshot(
                        module=top_dir,
                        files=[],
                        file_count=0,
                        total_loc=0,
                        total_functions=0,
                    )
                module_map[top_dir].files.append(f_snap.path)
                module_map[top_dir].file_count += 1
                module_map[top_dir].total_loc += f_snap.total_loc

        module_graph = dag_service.build_module_graph(root)
        dependencies = [
            DependencyEdge(from_module=module, to_module=imp)
            for module, node in module_graph.items()
            for imp in node.imports
        ]

        total_loc = sum(f.total_loc for f in files)
        total_functions = sum(f.function_count for f in files)
        total_files = len(files)

        metrics = StructureMetrics(
            total_files=total_files,
            total_loc=total_loc,
            total_functions=total_functions,
            python_files=total_files,
            shell_files=0,
            avg_file_loc=total_loc / total_files if total_files > 0 else 0.0,
            avg_functions_per_file=(
                total_functions / total_files if total_files > 0 else 0.0
            ),
        )

        snapshot = StructureSnapshot(
            snapshot_id=snapshot_id,
            branch=branch,
            commit=commit or "unknown",
            commit_short=commit_short,
            created_at=timestamp,
            root=root,
            files=files,
            modules=list(module_map.values()),
            dependencies=dependencies,
            metrics=metrics,
        )

        log.bind(files=len(files), modules=len(module_map)).success("Snapshot built")
        return snapshot

    except SnapshotError:
        raise
    except Exception as e:
        raise SnapshotError(str(e)) from e


def save_snapshot(snapshot: StructureSnapshot) -> Path:
    """Save snapshot to disk."""
    log = logger.bind(
        domain="snapshot", action="save", snapshot_id=snapshot.snapshot_id
    )
    log.info("Saving snapshot")

    try:
        _ensure_snapshot_dir()
        snapshot_dir = _get_snapshot_dir()
        latest_link = _get_latest_link_path()

        filename = f"{snapshot.snapshot_id}.json"
        filepath = snapshot_dir / filename
        filepath.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        latest_link.write_text(str(filepath), encoding="utf-8")

        log.bind(path=str(filepath)).success("Snapshot saved")
        return filepath
    except Exception as e:
        raise SnapshotError(f"Failed to save snapshot: {e}") from e


def load_snapshot(snapshot_id: str | None = None) -> StructureSnapshot:
    """Load a snapshot from disk."""
    log = logger.bind(domain="snapshot", action="load", snapshot_id=snapshot_id)
    log.info("Loading snapshot")

    try:
        snapshot_dir = _get_snapshot_dir()
        latest_link = _get_latest_link_path()

        if snapshot_id:
            filepath = snapshot_dir / f"{snapshot_id}.json"
        else:
            if not latest_link.exists():
                raise SnapshotNotFoundError("latest")
            filepath = Path(latest_link.read_text(encoding="utf-8").strip())

        if not filepath.exists():
            raise SnapshotNotFoundError(snapshot_id or "latest")

        data = json.loads(filepath.read_text(encoding="utf-8"))
        snapshot = StructureSnapshot.model_validate(data)
        log.success("Snapshot loaded")
        return snapshot

    except SnapshotNotFoundError:
        raise
    except json.JSONDecodeError as e:
        raise SnapshotError(f"Invalid snapshot JSON: {e}") from e
    except Exception as e:
        raise SnapshotError(f"Failed to load snapshot: {e}") from e


def list_snapshots(
    include_baselines: bool = False, limit: int | None = 50
) -> list[str]:
    """List available snapshot IDs (newest first).

    Args:
        include_baselines: If True, include auto-saved baselines in the list
        limit: Maximum number of snapshots to return (default: 50).
               Set to None to return all snapshots.

    Returns:
        List of snapshot IDs, sorted by creation time (newest first).
        Limited to `limit` entries if specified.
    """
    snapshots = []

    # Scan regular snapshots directory
    snapshot_dir = _get_snapshot_dir()
    if snapshot_dir.exists():
        for fp in snapshot_dir.glob("*.json"):
            meta = _read_snapshot_metadata(fp)
            if meta is None:
                continue
            if not include_baselines and meta.get("baseline_for"):
                continue
            snapshots.append(
                {
                    "id": meta.get("snapshot_id") or fp.stem,
                    "created_at": meta.get("created_at") or "",
                }
            )

    # Scan baselines directory if requested
    if include_baselines:
        baseline_dir = _get_baseline_dir()
        if baseline_dir.exists():
            for fp in baseline_dir.glob("*.json"):
                meta = _read_snapshot_metadata(fp)
                if meta is None:
                    continue
                snapshots.append(
                    {
                        "id": meta.get("snapshot_id") or fp.stem,
                        "created_at": meta.get("created_at") or "",
                    }
                )

    # Sort by creation time (newest first)
    snapshots.sort(key=lambda x: x["created_at"], reverse=True)

    # Apply limit if specified
    if limit is not None:
        snapshots = snapshots[:limit]

    return [s["id"] for s in snapshots]


# ---------------------------------------------------------------------------
# Snapshot lookup by branch (from snapshot_lookup.py)
# ---------------------------------------------------------------------------


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
    sanitized_branch = normalized_branch.replace("/", "-")

    # Stage 1: Glob pre-filter using branch name in filename
    pattern = str(snapshot_dir / f"*_{sanitized_branch}_*.json")
    candidate_paths = set(glob_mod.glob(pattern))

    # Stage 2: Load and verify branch field for narrowed candidates
    snapshots = _load_snapshots_for_branch(candidate_paths, normalized_branch, branch)

    # Fallback: the glob pre-filter assumes snapshot filenames embed the
    # branch name (see StructureSnapshot.generate_id). If no candidate
    # matched, scan remaining files to catch snapshots saved under other
    # naming conventions rather than silently returning None.
    if not snapshots:
        all_paths = {str(p) for p in snapshot_dir.glob("*.json")}
        snapshots = _load_snapshots_for_branch(
            all_paths - candidate_paths, normalized_branch, branch
        )

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


_METADATA_FIELDS = ("snapshot_id", "created_at", "branch", "commit", "baseline_for")


def _read_snapshot_metadata(filepath: Path) -> dict[str, str | None] | None:
    """Extract top-level string fields from a snapshot JSON file.

    Uses bounded head/tail reads instead of loading the full file,
    since metadata fields are concentrated at the beginning/end of the
    serialized JSON (StructureSnapshot). The large nested structures
    (files, modules, dependencies, metrics) are never deserialized.
    Returns None if the file cannot be read or has no recognizable metadata.
    """
    # --- Head read for early metadata fields ---
    try:
        file_size = filepath.stat().st_size
        head_size = min(4096, file_size)
        with filepath.open("r", encoding="utf-8") as f:
            head = f.read(head_size)
    except OSError:
        return None
    if not head.strip():
        return None

    try:
        metadata: dict[str, str | None] = {}
        for field in _METADATA_FIELDS:
            # baseline_for is the last field in StructureSnapshot (after metrics)
            # -> read from tail for large files
            source = head
            if field == "baseline_for" and file_size > head_size:
                try:
                    tail_size = min(2048, file_size)
                    with filepath.open("rb") as f:
                        f.seek(file_size - tail_size)
                        source = f.read(tail_size).decode("utf-8", errors="replace")
                except OSError:
                    source = head  # fallback to head

            m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', source)
            if m:
                metadata[field] = m.group(1)
            elif re.search(rf'"{field}"\s*:\s*null', source):
                metadata[field] = None
        return metadata if metadata else None
    except Exception:
        return None


def _load_snapshots_for_branch(
    paths: set[str], normalized_branch: str, branch: str
) -> list[dict[str, str]]:
    """Load snapshot metadata for files whose `branch` field matches."""
    snapshots: list[dict[str, str]] = []
    for fp_str in paths:
        fp = Path(fp_str)
        meta = _read_snapshot_metadata(fp)
        if meta is None:
            continue
        snapshot_branch = meta.get("branch") or ""
        if snapshot_branch == normalized_branch or snapshot_branch == branch:
            snapshots.append(
                {
                    "id": meta.get("snapshot_id") or fp.stem,
                    "created_at": meta.get("created_at") or "",
                    "branch": snapshot_branch,
                    "commit": meta.get("commit") or "",
                }
            )
    return snapshots


def save_branch_baseline(branch: str, force: bool = False) -> Path | None:
    """Build current snapshot and save as baseline for the specified branch.

    This function is called when a flow completes (PR merge or auto-complete).
    It builds a fresh snapshot and saves it with baseline_for tag.

    Args:
        branch: Branch name to save baseline for
        force: Force overwrite existing baseline (default: False)

    Returns:
        Path to saved baseline, or None if build failed
    """
    log = logger.bind(domain="snapshot", action="save_baseline", branch=branch)
    log.info("Saving branch baseline")

    try:
        snapshot = build_snapshot()
        snapshot.baseline_for = branch

        _ensure_baseline_dir()
        baseline_dir = _get_baseline_dir()

        # Sanitize branch name for filename safety
        safe_branch = branch.replace("/", "-")
        filename = f"baseline_{safe_branch}.json"
        filepath = baseline_dir / filename

        if filepath.exists() and not force:
            log.info("Baseline already exists, skipping (idempotent)")
            return filepath

        filepath.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")

        log.bind(path=str(filepath)).success("Branch baseline saved")
        return filepath

    except Exception as e:
        logger.warning(f"Failed to save branch baseline: {e}")
        return None


def load_branch_baseline(branch: str) -> StructureSnapshot | None:
    """Load the most recent baseline snapshot for a branch.

    Args:
        branch: Branch name to load baseline for

    Returns:
        StructureSnapshot for the branch baseline, or None if not found
    """
    log = logger.bind(domain="snapshot", action="load_baseline", branch=branch)
    log.info("Loading branch baseline")

    try:
        baseline_dir = _get_baseline_dir()
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


def build_snapshot_diff(
    base_branch: str = "main", current_branch: str | None = None
) -> StructureDiff | None:
    """Build snapshot diff for review context."""
    # Local import to avoid circular dependency:
    # snapshot_diff.py imports SnapshotError from snapshot_service
    from vibe3.analysis.snapshot_diff import compute_diff

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
