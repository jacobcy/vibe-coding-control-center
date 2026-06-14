"""Tests for snapshot diff section builder."""

import pytest

from vibe3.analysis.snapshot_diff_section import build_snapshot_diff_section
from vibe3.models.snapshot import (
    DependencyChange,
    DiffSummary,
    DiffWarning,
    FileChange,
    ModuleChange,
    StructureDiff,
)


@pytest.fixture
def sample_diff() -> StructureDiff:
    """Create a sample StructureDiff for testing."""
    return StructureDiff(
        baseline_id="2026-03-20T10-00-00_main_abc1234",
        baseline_branch="main",
        baseline_commit="abc1234",
        current_id="2026-03-24T15-30-00_feature_def5678",
        current_branch="feature/test",
        current_commit="def5678",
        created_at="2026-03-24T15:30:00",
        summary=DiffSummary(
            files_added=2,
            files_removed=1,
            files_modified=3,
            modules_added=1,
            modules_removed=0,
            modules_modified=1,
            dependencies_added=1,
            dependencies_removed=0,
            total_loc_delta=150,
            total_functions_delta=8,
        ),
        file_changes=[
            FileChange(
                path="src/vibe3/services/new_service.py",
                change_type="added",
                new_loc=100,
                new_function_count=5,
            ),
            FileChange(
                path="src/vibe3/commands/old_cmd.py",
                change_type="removed",
                old_loc=50,
                old_function_count=3,
            ),
            FileChange(
                path="src/vibe3/services/flow_service.py",
                change_type="modified",
                old_loc=200,
                new_loc=250,
                old_function_count=10,
                new_function_count=12,
            ),
        ],
        module_changes=[
            ModuleChange(
                module="vibe3.services",
                change_type="modified",
                old_file_count=5,
                new_file_count=6,
                old_loc=500,
                new_loc=600,
            ),
        ],
        dependency_changes=[
            DependencyChange(
                change_type="added",
                from_module="vibe3.services",
                to_module="vibe3.utils",
            ),
        ],
        warnings=[
            DiffWarning(
                type="module_growth",
                severity="warning",
                message="Module vibe3.services grew by 100 lines",
                module="vibe3.services",
            ),
        ],
    )


def test_build_snapshot_diff_section_none():
    """Test that None input returns None."""
    result = build_snapshot_diff_section(None)
    assert result is None


@pytest.mark.parametrize(
    "section_name,expected_content",
    [
        pytest.param(
            "basic",
            [
                "Structure Changes (Snapshot Diff)",
                "2026-03-20T10-00-00_main_abc1234",
                "main",
                "2026-03-24T15-30-00_feature_def5678",
                "feature/test",
            ],
            id="basic_info",
        ),
        pytest.param(
            "file_changes",
            [
                "### File Changes",
                "Added: 2",
                "Removed: 1",
                "Modified: 3",
                "LOC delta: +150",
                "Functions delta: +8",
            ],
            id="file_changes_section",
        ),
        pytest.param(
            "module_changes",
            ["### Module Changes", "Added: 1", "Modified: 1"],
            id="module_changes_section",
        ),
        pytest.param(
            "dependency_changes",
            ["### Dependency Changes", "vibe3.services → vibe3.utils"],
            id="dependency_changes_section",
        ),
        pytest.param(
            "file_details",
            [
                "### File Details (by module)",
                "+ src/vibe3/services/new_service.py",
                "- src/vibe3/commands/old_cmd.py",
                "~ src/vibe3/services/flow_service.py",
            ],
            id="file_details_section",
        ),
        pytest.param(
            "warnings",
            ["### Warnings", "[WARNING]", "Module vibe3.services grew by 100 lines"],
            id="warnings_section",
        ),
    ],
)
def test_build_snapshot_diff_section_sections(
    sample_diff: StructureDiff, section_name: str, expected_content: list[str]
):
    """Test that all expected sections appear in the output."""
    result = build_snapshot_diff_section(sample_diff)
    assert result is not None
    for content in expected_content:
        assert content in result


@pytest.mark.parametrize(
    "has_module_changes,has_warnings",
    [
        pytest.param(False, True, id="no_module_changes"),
        pytest.param(True, False, id="no_warnings"),
    ],
)
def test_build_snapshot_diff_section_optional_sections(
    has_module_changes: bool, has_warnings: bool
):
    """Test diff with optional sections omitted."""
    diff = StructureDiff(
        baseline_id="baseline",
        baseline_branch="main",
        baseline_commit="abc1234",
        current_id="current",
        current_branch="feature",
        current_commit="def5678",
        created_at="2026-03-24T15:30:00",
        summary=DiffSummary(
            files_added=1,
            files_removed=0,
            files_modified=0,
            modules_added=1 if has_module_changes else 0,
            modules_removed=0,
            modules_modified=0,
        ),
        file_changes=[
            FileChange(
                path="src/new.py",
                change_type="added",
                new_loc=50,
                new_function_count=3,
            ),
        ],
        module_changes=(
            [
                ModuleChange(
                    module="vibe3.services",
                    change_type="added",
                    old_file_count=0,
                    new_file_count=1,
                    old_loc=0,
                    new_loc=50,
                ),
            ]
            if has_module_changes
            else []
        ),
        warnings=(
            [
                DiffWarning(
                    type="module_growth",
                    severity="warning",
                    message="Test warning",
                    module="vibe3.services",
                ),
            ]
            if has_warnings
            else []
        ),
    )

    result = build_snapshot_diff_section(diff)
    assert result is not None
    if not has_module_changes:
        assert "### Module Changes" not in result
    if not has_warnings:
        assert "### Warnings" not in result


def test_build_snapshot_diff_section_many_files():
    """Test diff with more than 10 files shows truncation message."""
    file_changes = [
        FileChange(
            path=f"src/file{i}.py",
            change_type="added",
            new_loc=10,
            new_function_count=1,
        )
        for i in range(15)
    ]

    diff = StructureDiff(
        baseline_id="baseline",
        baseline_branch="main",
        baseline_commit="abc1234",
        current_id="current",
        current_branch="feature",
        current_commit="def5678",
        created_at="2026-03-24T15:30:00",
        summary=DiffSummary(files_added=15),
        file_changes=file_changes,
    )

    result = build_snapshot_diff_section(diff)
    assert result is not None
    assert "... and 12 more files" in result
