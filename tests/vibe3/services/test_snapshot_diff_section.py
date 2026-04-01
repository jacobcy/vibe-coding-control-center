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


def test_build_snapshot_diff_section_basic(sample_diff: StructureDiff):
    """Test basic snapshot diff section generation."""
    result = build_snapshot_diff_section(sample_diff)

    assert result is not None
    assert "Structure Changes (Snapshot Diff)" in result
    assert "2026-03-20T10-00-00_main_abc1234" in result
    assert "2026-03-24T15-30-00_feature_def5678" in result
    assert "main" in result
    assert "feature/test" in result


def test_build_snapshot_diff_section_file_changes(sample_diff: StructureDiff):
    """Test file changes summary is included."""
    result = build_snapshot_diff_section(sample_diff)

    assert "### File Changes" in result
    assert "Added: 2" in result
    assert "Removed: 1" in result
    assert "Modified: 3" in result
    assert "LOC delta: +150" in result
    assert "Functions delta: +8" in result


def test_build_snapshot_diff_section_module_changes(sample_diff: StructureDiff):
    """Test module changes summary is included."""
    result = build_snapshot_diff_section(sample_diff)

    assert "### Module Changes" in result
    assert "Added: 1" in result
    assert "Modified: 1" in result


def test_build_snapshot_diff_section_dependency_changes(sample_diff: StructureDiff):
    """Test dependency changes are included."""
    result = build_snapshot_diff_section(sample_diff)

    assert "### Dependency Changes" in result
    assert "vibe3.services → vibe3.utils" in result


def test_build_snapshot_diff_section_file_details(sample_diff: StructureDiff):
    """Test file details are included."""
    result = build_snapshot_diff_section(sample_diff)

    assert "### File Details (Top 10)" in result
    assert "+ src/vibe3/services/new_service.py" in result
    assert "- src/vibe3/commands/old_cmd.py" in result
    assert "~ src/vibe3/services/flow_service.py" in result


def test_build_snapshot_diff_section_warnings(sample_diff: StructureDiff):
    """Test warnings are included."""
    result = build_snapshot_diff_section(sample_diff)

    assert "### Warnings" in result
    assert "[WARNING]" in result
    assert "Module vibe3.services grew by 100 lines" in result


def test_build_snapshot_diff_section_no_module_changes():
    """Test diff without module changes."""
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
            modules_added=0,
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
    )

    result = build_snapshot_diff_section(diff)
    assert result is not None
    assert "### Module Changes" not in result


def test_build_snapshot_diff_section_no_warnings():
    """Test diff without warnings."""
    diff = StructureDiff(
        baseline_id="baseline",
        baseline_branch="main",
        baseline_commit="abc1234",
        current_id="current",
        current_branch="feature",
        current_commit="def5678",
        created_at="2026-03-24T15:30:00",
        summary=DiffSummary(files_added=1),
        file_changes=[
            FileChange(
                path="src/new.py",
                change_type="added",
                new_loc=50,
                new_function_count=3,
            ),
        ],
    )

    result = build_snapshot_diff_section(diff)
    assert result is not None
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
    assert "... and 5 more files" in result
