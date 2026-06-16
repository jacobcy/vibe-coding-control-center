"""Tests for compute_diff function."""

from vibe3.analysis.snapshot_diff import compute_diff
from vibe3.models.snapshot import (
    DependencyEdge,
    DiffSummary,
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


def test_diff_summary_from_metrics():
    """Test DiffSummary.from_metrics classmethod."""
    baseline = StructureMetrics(
        total_files=5,
        total_loc=100,
        total_functions=5,
        python_files=4,
        shell_files=1,
    )

    current = StructureMetrics(
        total_files=10,
        total_loc=350,
        total_functions=17,
        python_files=9,
        shell_files=1,
    )

    result = DiffSummary.from_metrics(baseline, current)

    # Should have only metric deltas populated
    assert result.total_loc_delta == 250  # 350 - 100
    assert result.total_functions_delta == 12  # 17 - 5

    # All other fields should be 0 (default)
    assert result.files_added == 0
    assert result.files_removed == 0
    assert result.files_modified == 0
    assert result.modules_added == 0
    assert result.modules_removed == 0
    assert result.modules_modified == 0
    assert result.dependencies_added == 0
    assert result.dependencies_removed == 0


def test_diff_summary_from_metrics_negative_delta():
    """Test DiffSummary.from_metrics with code shrinkage (negative delta)."""
    baseline = StructureMetrics(
        total_files=10,
        total_loc=350,
        total_functions=17,
    )
    current = StructureMetrics(
        total_files=5,
        total_loc=100,
        total_functions=5,
    )

    result = DiffSummary.from_metrics(baseline, current)

    assert result.total_loc_delta == -250  # 100 - 350
    assert result.total_functions_delta == -12  # 5 - 17


def test_diff_summary_add():
    """Test DiffSummary.__add__ sums all fields correctly."""
    a = DiffSummary(
        files_added=1,
        files_removed=0,
        files_modified=2,
        modules_added=1,
        modules_removed=0,
        modules_modified=1,
        dependencies_added=1,
        dependencies_removed=0,
        total_loc_delta=100,
        total_functions_delta=10,
    )
    b = DiffSummary(
        files_added=0,
        files_removed=1,
        files_modified=1,
        modules_added=0,
        modules_removed=1,
        modules_modified=0,
        dependencies_added=0,
        dependencies_removed=1,
        total_loc_delta=-30,
        total_functions_delta=-3,
    )

    result = a + b

    assert result.files_added == 1
    assert result.files_removed == 1
    assert result.files_modified == 3
    assert result.modules_added == 1
    assert result.modules_removed == 1
    assert result.modules_modified == 1
    assert result.dependencies_added == 1
    assert result.dependencies_removed == 1
    assert result.total_loc_delta == 70
    assert result.total_functions_delta == 7


def test_compute_diff_identical_snapshots():
    """Test compute_diff with identical snapshots (zero delta edge case)."""
    snapshot = StructureSnapshot(
        snapshot_id="2026-03-20T10-00-00_main_abc1234",
        branch="main",
        commit="abc1234567890",
        commit_short="abc1234",
        created_at="2026-03-20T10:00:00",
        root="src/vibe3",
        files=[
            FileSnapshot(
                path="services/service.py",
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
                files=["services/service.py"],
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

    # Compare identical snapshots
    diff = compute_diff(snapshot, snapshot)

    # Should have zero deltas
    assert diff.summary.total_loc_delta == 0
    assert diff.summary.total_functions_delta == 0

    # Should have no changes
    assert diff.summary.files_added == 0
    assert diff.summary.files_removed == 0
    assert diff.summary.files_modified == 0
    assert diff.summary.modules_added == 0
    assert diff.summary.modules_removed == 0
    assert diff.summary.modules_modified == 0
    assert diff.summary.dependencies_added == 0
    assert diff.summary.dependencies_removed == 0

    # Should have empty change lists
    assert len(diff.file_changes) == 0
    assert len(diff.module_changes) == 0
    assert len(diff.dependency_changes) == 0


def test_module_growth_warning_threshold():
    """Test that module_growth warnings respect the configured threshold."""
    baseline = StructureSnapshot(
        snapshot_id="base",
        branch="main",
        commit="a" * 13,
        commit_short="a" * 7,
        created_at="2026-01-01T00:00:00",
        root="src/vibe3",
        files=[],
        modules=[
            ModuleSnapshot(
                module="services",
                file_count=1,
                total_loc=100,
                total_functions=5,
                files=["s.py"],
            )
        ],
        dependencies=[],
        metrics=StructureMetrics(total_files=1, total_loc=100, total_functions=5),
    )
    current = StructureSnapshot(
        snapshot_id="cur",
        branch="feature",
        commit="b" * 13,
        commit_short="b" * 7,
        created_at="2026-01-02T00:00:00",
        root="src/vibe3",
        files=[],
        modules=[
            ModuleSnapshot(
                module="services",
                file_count=1,
                total_loc=201,
                total_functions=5,
                files=["s.py"],
            )
        ],
        dependencies=[],
        metrics=StructureMetrics(total_files=1, total_loc=201, total_functions=5),
    )
    diff = compute_diff(baseline, current)
    warnings = [w for w in diff.warnings if w.type == "module_growth"]
    assert len(warnings) == 1  # 201 - 100 = 101 > 100


def test_module_growth_warning_threshold_boundary():
    """Test module_growth warnings at threshold boundaries."""
    # Growth = 100 (at threshold, should NOT warn: > not >=)
    baseline = StructureSnapshot(
        snapshot_id="base",
        branch="main",
        commit="a" * 13,
        commit_short="a" * 7,
        created_at="2026-01-01T00:00:00",
        root="src/vibe3",
        files=[],
        modules=[
            ModuleSnapshot(
                module="services",
                file_count=1,
                total_loc=100,
                total_functions=5,
                files=["s.py"],
            )
        ],
        dependencies=[],
        metrics=StructureMetrics(total_files=1, total_loc=100, total_functions=5),
    )

    # Test at threshold (100) - should NOT warn
    current_at = StructureSnapshot(
        snapshot_id="cur",
        branch="feature",
        commit="b" * 13,
        commit_short="b" * 7,
        created_at="2026-01-02T00:00:00",
        root="src/vibe3",
        files=[],
        modules=[
            ModuleSnapshot(
                module="services",
                file_count=1,
                total_loc=200,  # 200 - 100 = 100
                total_functions=5,
                files=["s.py"],
            )
        ],
        dependencies=[],
        metrics=StructureMetrics(total_files=1, total_loc=200, total_functions=5),
    )
    diff_at = compute_diff(baseline, current_at)
    warnings_at = [w for w in diff_at.warnings if w.type == "module_growth"]
    assert len(warnings_at) == 0  # growth=100, NOT > 100

    # Test above threshold (101) - should warn
    current_above = StructureSnapshot(
        snapshot_id="cur",
        branch="feature",
        commit="c" * 13,
        commit_short="c" * 7,
        created_at="2026-01-03T00:00:00",
        root="src/vibe3",
        files=[],
        modules=[
            ModuleSnapshot(
                module="services",
                file_count=1,
                total_loc=201,  # 201 - 100 = 101
                total_functions=5,
                files=["s.py"],
            )
        ],
        dependencies=[],
        metrics=StructureMetrics(total_files=1, total_loc=201, total_functions=5),
    )
    diff_above = compute_diff(baseline, current_above)
    warnings_above = [w for w in diff_above.warnings if w.type == "module_growth"]
    assert len(warnings_above) == 1  # growth=101 > 100
    assert warnings_above[0].module == "services"
    assert warnings_above[0].details["old_loc"] == 100
    assert warnings_above[0].details["new_loc"] == 201
