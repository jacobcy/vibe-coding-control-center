"""Snapshot diff service - Compute differences between snapshots."""

from datetime import datetime, timezone

from loguru import logger

from vibe3.models.snapshot import (
    DependencyChange,
    DiffSummary,
    DiffWarning,
    FileChange,
    ModuleChange,
    StructureDiff,
    StructureSnapshot,
)
from vibe3.services.snapshot_service import SnapshotError


def _diff_files(
    baseline: StructureSnapshot, current: StructureSnapshot
) -> tuple[list[FileChange], DiffSummary]:
    """Compute file-level differences between snapshots."""
    baseline_files = {f.path: f for f in baseline.files}
    current_files = {f.path: f for f in current.files}

    baseline_paths = set(baseline_files.keys())
    current_paths = set(current_files.keys())

    added = current_paths - baseline_paths
    removed = baseline_paths - current_paths
    common = baseline_paths & current_paths

    file_changes: list[FileChange] = []
    summary = DiffSummary()

    for path in added:
        f = current_files[path]
        file_changes.append(
            FileChange(
                path=path,
                change_type="added",
                old_loc=None,
                new_loc=f.total_loc,
                old_function_count=None,
                new_function_count=f.function_count,
            )
        )
        summary.files_added += 1

    for path in removed:
        f = baseline_files[path]
        file_changes.append(
            FileChange(
                path=path,
                change_type="removed",
                old_loc=f.total_loc,
                new_loc=None,
                old_function_count=f.function_count,
                new_function_count=None,
            )
        )
        summary.files_removed += 1

    for path in common:
        bf = baseline_files[path]
        cf = current_files[path]
        if bf.total_loc != cf.total_loc or bf.function_count != cf.function_count:
            file_changes.append(
                FileChange(
                    path=path,
                    change_type="modified",
                    old_loc=bf.total_loc,
                    new_loc=cf.total_loc,
                    old_function_count=bf.function_count,
                    new_function_count=cf.function_count,
                )
            )
            summary.files_modified += 1

    summary.total_loc_delta = current.metrics.total_loc - baseline.metrics.total_loc
    summary.total_functions_delta = (
        current.metrics.total_functions - baseline.metrics.total_functions
    )

    return file_changes, summary


def _diff_modules(
    baseline: StructureSnapshot, current: StructureSnapshot
) -> tuple[list[ModuleChange], DiffSummary, list[DiffWarning]]:
    """Compute module-level differences between snapshots."""
    baseline_modules = {m.module: m for m in baseline.modules}
    current_modules = {m.module: m for m in current.modules}

    baseline_names = set(baseline_modules.keys())
    current_names = set(current_modules.keys())

    added = current_names - baseline_names
    removed = baseline_names - current_names
    common = baseline_names & current_names

    module_changes: list[ModuleChange] = []
    warnings: list[DiffWarning] = []
    summary = DiffSummary()

    for name in added:
        m = current_modules[name]
        module_changes.append(
            ModuleChange(
                module=name,
                change_type="added",
                old_file_count=None,
                new_file_count=m.file_count,
                old_loc=None,
                new_loc=m.total_loc,
            )
        )
        summary.modules_added += 1

    for name in removed:
        m = baseline_modules[name]
        module_changes.append(
            ModuleChange(
                module=name,
                change_type="removed",
                old_file_count=m.file_count,
                new_file_count=None,
                old_loc=m.total_loc,
                new_loc=None,
            )
        )
        summary.modules_removed += 1

    for name in common:
        bm = baseline_modules[name]
        cm = current_modules[name]
        if bm.total_loc != cm.total_loc or bm.file_count != cm.file_count:
            module_changes.append(
                ModuleChange(
                    module=name,
                    change_type="modified",
                    old_file_count=bm.file_count,
                    new_file_count=cm.file_count,
                    old_loc=bm.total_loc,
                    new_loc=cm.total_loc,
                )
            )
            summary.modules_modified += 1

            growth = cm.total_loc - bm.total_loc
            if growth > 100:
                warnings.append(
                    DiffWarning(
                        type="module_growth",
                        severity="warning",
                        message=f"Module {name} grew by {growth} lines",
                        module=name,
                        details={"old_loc": bm.total_loc, "new_loc": cm.total_loc},
                    )
                )

    return module_changes, summary, warnings


def _diff_dependencies(
    baseline: StructureSnapshot, current: StructureSnapshot
) -> tuple[list[DependencyChange], DiffSummary]:
    """Compute dependency differences between snapshots."""
    baseline_deps = {(d.from_module, d.to_module) for d in baseline.dependencies}
    current_deps = {(d.from_module, d.to_module) for d in current.dependencies}

    added = current_deps - baseline_deps
    removed = baseline_deps - current_deps

    dependency_changes: list[DependencyChange] = []
    summary = DiffSummary()

    for from_mod, to_mod in added:
        dependency_changes.append(
            DependencyChange(
                change_type="added", from_module=from_mod, to_module=to_mod
            )
        )
        summary.dependencies_added += 1

    for from_mod, to_mod in removed:
        dependency_changes.append(
            DependencyChange(
                change_type="removed", from_module=from_mod, to_module=to_mod
            )
        )
        summary.dependencies_removed += 1

    return dependency_changes, summary


def compute_diff(
    baseline: StructureSnapshot, current: StructureSnapshot
) -> StructureDiff:
    """Compute difference between two snapshots.

    Args:
        baseline: Baseline snapshot (earlier state)
        current: Current snapshot (later state)

    Returns:
        StructureDiff with all changes

    Raises:
        SnapshotError: If diff computation fails
    """
    log = logger.bind(
        domain="snapshot",
        action="diff",
        baseline=baseline.snapshot_id,
        current=current.snapshot_id,
    )
    log.info("Computing structure diff")

    try:
        file_changes, file_summary = _diff_files(baseline, current)
        module_changes, module_summary, warnings = _diff_modules(baseline, current)
        dep_changes, dep_summary = _diff_dependencies(baseline, current)

        summary = DiffSummary(
            files_added=file_summary.files_added,
            files_removed=file_summary.files_removed,
            files_modified=file_summary.files_modified,
            modules_added=module_summary.modules_added,
            modules_removed=module_summary.modules_removed,
            modules_modified=module_summary.modules_modified,
            dependencies_added=dep_summary.dependencies_added,
            dependencies_removed=dep_summary.dependencies_removed,
            total_loc_delta=file_summary.total_loc_delta,
            total_functions_delta=file_summary.total_functions_delta,
        )

        diff = StructureDiff(
            baseline_id=baseline.snapshot_id,
            baseline_branch=baseline.branch,
            baseline_commit=baseline.commit,
            current_id=current.snapshot_id,
            current_branch=current.branch,
            current_commit=current.commit,
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            summary=summary,
            file_changes=file_changes,
            module_changes=module_changes,
            dependency_changes=dep_changes,
            warnings=warnings,
        )

        log.bind(
            files_changed=len(file_changes),
            modules_changed=len(module_changes),
            deps_changed=len(dep_changes),
        ).success("Diff computed")

        return diff

    except Exception as e:
        raise SnapshotError(f"Failed to compute diff: {e}") from e
