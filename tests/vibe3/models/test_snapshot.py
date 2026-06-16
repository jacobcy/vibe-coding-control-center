"""Tests for snapshot models."""

from vibe3.models.snapshot import DiffSummary, StructureMetrics


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
    """Test that adding two DiffSummary instances sums all fields."""
    a = DiffSummary(
        files_added=1,
        files_removed=2,
        files_modified=3,
        modules_added=4,
        modules_removed=5,
        modules_modified=6,
        dependencies_added=7,
        dependencies_removed=8,
        total_loc_delta=100,
        total_functions_delta=50,
    )
    b = DiffSummary(
        files_added=10,
        files_removed=20,
        files_modified=30,
        modules_added=40,
        modules_removed=50,
        modules_modified=60,
        dependencies_added=70,
        dependencies_removed=80,
        total_loc_delta=200,
        total_functions_delta=150,
    )

    result = a + b

    assert result.files_added == 11
    assert result.files_removed == 22
    assert result.files_modified == 33
    assert result.modules_added == 44
    assert result.modules_removed == 55
    assert result.modules_modified == 66
    assert result.dependencies_added == 77
    assert result.dependencies_removed == 88
    assert result.total_loc_delta == 300
    assert result.total_functions_delta == 200


def test_diff_summary_add_defaults():
    """Test that adding two default DiffSummary instances returns all zeros."""
    a = DiffSummary()
    b = DiffSummary()

    result = a + b

    assert result.files_added == 0
    assert result.files_removed == 0
    assert result.files_modified == 0
    assert result.modules_added == 0
    assert result.modules_removed == 0
    assert result.modules_modified == 0
    assert result.dependencies_added == 0
    assert result.dependencies_removed == 0
    assert result.total_loc_delta == 0
    assert result.total_functions_delta == 0


def test_diff_summary_add_commutative():
    """Test that DiffSummary addition is commutative."""
    a = DiffSummary(
        files_added=1,
        files_removed=2,
        total_loc_delta=100,
        total_functions_delta=50,
    )
    b = DiffSummary(
        files_added=10,
        files_removed=20,
        total_loc_delta=200,
        total_functions_delta=150,
    )

    result_ab = a + b
    result_ba = b + a

    assert result_ab.files_added == result_ba.files_added
    assert result_ab.files_removed == result_ba.files_removed
    assert result_ab.total_loc_delta == result_ba.total_loc_delta
    assert result_ab.total_functions_delta == result_ba.total_functions_delta
