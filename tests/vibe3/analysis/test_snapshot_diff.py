"""Tests for compute_diff function."""

from vibe3.analysis.snapshot_diff import compute_diff
from vibe3.models.snapshot import (
    DependencyEdge,
    FileSnapshot,
    ModuleSnapshot,
    StructureMetrics,
    StructureSnapshot,
)


def test_compute_diff_merges_summaries():
    """Test that compute_diff correctly merges sub-summaries."""
    # Create baseline snapshot
    baseline = StructureSnapshot(
        snapshot_id="2026-03-20T10-00-00_main_abc1234",
        branch="main",
        commit="abc1234567890",
        commit_short="abc1234",
        created_at="2026-03-20T10:00:00",
        root="src/vibe3",
        files=[
            FileSnapshot(
                path="services/old_service.py",
                language="python",
                total_loc=100,
                function_count=5,
            ),
        ],
        modules=[
            ModuleSnapshot(
                module="services",
                file_count=1,
                total_loc=100,
                total_functions=5,
                files=["services/old_service.py"],
            ),
        ],
        dependencies=[
            DependencyEdge(from_module="services", to_module="utils"),
        ],
        metrics=StructureMetrics(
            total_files=1,
            total_loc=100,
            total_functions=5,
        ),
    )

    # Create current snapshot with changes
    current = StructureSnapshot(
        snapshot_id="2026-03-24T15-30-00_feature_def5678",
        branch="feature/test",
        commit="def5678901234",
        commit_short="def5678",
        created_at="2026-03-24T15:30:00",
        root="src/vibe3",
        files=[
            FileSnapshot(
                path="services/old_service.py",
                language="python",
                total_loc=150,  # Modified
                function_count=7,  # Modified
            ),
            FileSnapshot(
                path="services/new_service.py",
                language="python",
                total_loc=200,
                function_count=10,
            ),
        ],
        modules=[
            ModuleSnapshot(
                module="services",
                file_count=2,  # Changed
                total_loc=350,  # Changed
                total_functions=17,  # Changed
                files=["services/old_service.py", "services/new_service.py"],
            ),
            ModuleSnapshot(
                module="commands",
                file_count=1,
                total_loc=50,
                total_functions=2,
                files=["commands/new_cmd.py"],
            ),
        ],
        dependencies=[
            DependencyEdge(from_module="services", to_module="utils"),
            DependencyEdge(from_module="services", to_module="models"),
        ],
        metrics=StructureMetrics(
            total_files=2,
            total_loc=350,
            total_functions=17,
        ),
    )

    # Compute diff
    diff = compute_diff(baseline, current)

    # Verify summary has correctly merged counts
    # File changes: 1 added, 0 removed, 1 modified
    assert diff.summary.files_added == 1
    assert diff.summary.files_removed == 0
    assert diff.summary.files_modified == 1

    # Module changes: 1 added, 0 removed, 1 modified
    assert diff.summary.modules_added == 1
    assert diff.summary.modules_removed == 0
    assert diff.summary.modules_modified == 1

    # Dependency changes: 1 added, 0 removed
    assert diff.summary.dependencies_added == 1
    assert diff.summary.dependencies_removed == 0

    # LOC and function deltas
    assert diff.summary.total_loc_delta == 250  # 350 - 100 = 250
    assert diff.summary.total_functions_delta == 12  # 17 - 5 = 12
