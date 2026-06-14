"""Snapshot diff section builder for review context.

This module provides the build_snapshot_diff_section() function
to format StructureDiff data for review context.
"""

from vibe3.models import StructureDiff

_MAX_FILES_PER_MODULE = 3
_MAX_TOTAL_FILES = 15


def _extract_module(file_path: str) -> str:
    """Extract top-level module from file path."""
    parts = file_path.split("/")
    if len(parts) > 1:
        return parts[0]
    return "other"


def _group_files_by_module(
    file_changes: list,
) -> list[list]:
    """Group file changes by top-level module.

    Each module is limited to _MAX_FILES_PER_MODULE entries.
    """
    from collections import OrderedDict

    groups: OrderedDict = OrderedDict()
    for fc in file_changes:
        module = _extract_module(fc.path)
        if module not in groups:
            groups[module] = []
        if len(groups[module]) < _MAX_FILES_PER_MODULE:
            groups[module].append(fc)

    result: list[list] = []
    for module, changes in groups.items():
        result.append(changes)
    return result


def build_snapshot_diff_section(structure_diff: StructureDiff | None) -> str | None:
    """Build snapshot diff section for review context.

    This replaces the AST analysis section when snapshot diff is available,
    providing richer structure-level change information.

    Args:
        structure_diff: StructureDiff object containing file/module/dependency changes

    Returns:
        Formatted snapshot diff section or None if no diff provided
    """
    if not structure_diff:
        return None

    parts: list[str] = []
    summary = structure_diff.summary

    parts.append("## Structure Changes (Snapshot Diff)")
    baseline_id = structure_diff.baseline_id
    baseline_branch = structure_diff.baseline_branch
    current_id = structure_diff.current_id
    current_branch = structure_diff.current_branch
    parts.append(
        f"**Baseline**: `{baseline_id}` ({baseline_branch})\n"
        f"**Current**: `{current_id}` ({current_branch})\n"
        f"**Time**: {structure_diff.created_at}"
    )

    parts.append(
        f"### File Changes\n"
        f"- Added: {summary.files_added}\n"
        f"- Removed: {summary.files_removed}\n"
        f"- Modified: {summary.files_modified}\n"
        f"- LOC delta: {summary.total_loc_delta:+d}\n"
        f"- Functions delta: {summary.total_functions_delta:+d}"
    )

    if summary.modules_added + summary.modules_removed + summary.modules_modified > 0:
        parts.append(
            f"### Module Changes\n"
            f"- Added: {summary.modules_added}\n"
            f"- Removed: {summary.modules_removed}\n"
            f"- Modified: {summary.modules_modified}"
        )

    if structure_diff.dependency_changes:
        deps_added = [
            d for d in structure_diff.dependency_changes if d.change_type == "added"
        ]
        deps_removed = [
            d for d in structure_diff.dependency_changes if d.change_type == "removed"
        ]
        dep_parts = []
        if deps_added:
            dep_parts.append(f"**Added** ({len(deps_added)}):")
            for dep in deps_added:
                dep_parts.append(f"  - {dep.from_module} → {dep.to_module}")
        if deps_removed:
            dep_parts.append(f"**Removed** ({len(deps_removed)}):")
            for dep in deps_removed:
                dep_parts.append(f"  - {dep.from_module} → {dep.to_module}")
        parts.append("### Dependency Changes\n" + "\n".join(dep_parts))

    if structure_diff.file_changes:
        module_groups = _group_files_by_module(structure_diff.file_changes)
        file_parts = []
        shown = 0
        for group in module_groups:
            if not group:
                continue
            module = _extract_module(group[0].path)
            if len(module_groups) > 1:
                file_parts.append(f"  [{module}/]")
            for fc in group:
                if fc.change_type == "added":
                    entry = (
                        f"    + {fc.path} "
                        f"(+{fc.new_loc} LOC, +{fc.new_function_count} funcs)"
                    )
                    file_parts.append(entry)
                elif fc.change_type == "removed":
                    entry = (
                        f"    - {fc.path} "
                        f"(-{fc.old_loc} LOC, -{fc.old_function_count} funcs)"
                    )
                    file_parts.append(entry)
                else:
                    loc_delta = (fc.new_loc or 0) - (fc.old_loc or 0)
                    func_delta = (fc.new_function_count or 0) - (
                        fc.old_function_count or 0
                    )
                    entry = (
                        f"    ~ {fc.path} "
                        f"({loc_delta:+d} LOC, {func_delta:+d} funcs)"
                    )
                    file_parts.append(entry)
                shown += 1
                if shown >= _MAX_TOTAL_FILES:
                    break
            if shown >= _MAX_TOTAL_FILES:
                break
        total = len(structure_diff.file_changes)
        if total > shown:
            remaining = total - shown
            file_parts.append(f"  ... and {remaining} more files")
        parts.append("### File Details (by module)\n" + "\n".join(file_parts))

    if structure_diff.warnings:
        warning_parts = []
        for w in structure_diff.warnings:
            warning_parts.append(f"- [{w.severity.upper()}] {w.message}")
        parts.append("### Warnings\n" + "\n".join(warning_parts))

    return "\n\n".join(parts)
