"""Snapshot service - Build, load, and manage structure snapshots."""

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from vibe3.clients.git_client import GitClient
from vibe3.exceptions import VibeError
from vibe3.models.snapshot import (
    DependencyEdge,
    FileSnapshot,
    FunctionSnapshot,
    ModuleSnapshot,
    StructureMetrics,
    StructureSnapshot,
)
from vibe3.services import dag_service, structure_service


class SnapshotError(VibeError):
    """Snapshot operation failed."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Snapshot error: {details}", recoverable=False)


class SnapshotNotFoundError(SnapshotError):
    """Snapshot not found."""

    def __init__(self, snapshot_id: str) -> None:
        super().__init__(f"Snapshot not found: {snapshot_id}")


SNAPSHOT_DIR_NAME = "vibe3/structure/snapshots"
LATEST_LINK_NAME = "vibe3/structure/latest.json"


def _get_snapshot_dir() -> Path:
    git = GitClient()
    return Path(git.get_git_common_dir()) / SNAPSHOT_DIR_NAME


def _get_latest_link_path() -> Path:
    git = GitClient()
    return Path(git.get_git_common_dir()) / LATEST_LINK_NAME


def _ensure_snapshot_dir() -> None:
    _get_snapshot_dir().mkdir(parents=True, exist_ok=True)


def _get_module_from_path(file_path: str) -> str:
    p = Path(file_path)
    if "src/vibe3" in str(p):
        parts = str(p).split("src/vibe3/")
        if len(parts) > 1:
            module_parts = parts[1].split("/")
            if len(module_parts) > 1:
                return "vibe3." + ".".join(module_parts[:-1])
            return "vibe3"
    return "vibe3"


def build_snapshot(root: str = "src/vibe3") -> StructureSnapshot:
    """Build a structure snapshot from the current codebase."""
    log = logger.bind(domain="snapshot", action="build", root=root)
    log.info("Building structure snapshot")

    try:
        git = GitClient()
        branch = git.get_current_branch()
        commit = git.get_current_commit()
        commit_short = commit[:7] if commit else "unknown"
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        snapshot_id = StructureSnapshot.generate_id(branch, commit_short, timestamp)

        file_structures = structure_service.collect_python_file_structures(root)
        files: list[FileSnapshot] = []
        module_map: dict[str, ModuleSnapshot] = {}

        for file_struct in file_structures:
            rel_path = file_struct.path
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

            module = _get_module_from_path(rel_path)
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


def list_snapshots() -> list[str]:
    """List all available snapshot IDs (newest first)."""
    snapshot_dir = _get_snapshot_dir()
    if not snapshot_dir.exists():
        return []

    snapshots = []
    for fp in snapshot_dir.glob("*.json"):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            snapshots.append(
                {
                    "id": data.get("snapshot_id", fp.stem),
                    "created_at": data.get("created_at", ""),
                }
            )
        except (json.JSONDecodeError, KeyError):
            continue

    snapshots.sort(key=lambda x: x["created_at"], reverse=True)
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
